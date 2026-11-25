import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ASSETS = Path(__file__).resolve().parents[1] / 'scientific-code-to-notebook/assets'
spec = importlib.util.spec_from_file_location('input_adapter', ASSETS / 'input_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class InputAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'observations.csv'
        self.data.write_text('id,condition,length\n001,A,3\n002,B,NA\n')
        self.config = {'dataset_id': 'test-fixture', 'path': self.data.name,
                       'source': 'internal unit-test fixture, not research data',
                       'source_type': 'user_data', 'role': 'method_transfer',
                       'sha256': adapter.digest(self.data), 'expected_rows': 2,
                       'columns': {'sample_id': 'id', 'group': 'condition', 'value': 'length'},
                       'units': {'value': 'mm'}, 'missing_values': ['NA']}

    def load(self, config=None):
        path = self.root / 'config.json'
        path.write_text(json.dumps(config if config is not None else self.config))
        return adapter.load_input(path)

    def test_real_observations_are_bundled_and_identified(self):
        rows, evidence = adapter.load_input(ASSETS / 'penguins_input.json')
        self.assertEqual(len(rows), 344)
        self.assertEqual(sum(row['value'] != '' for row in rows), 342)
        self.assertEqual(evidence['role'], 'input_example')
        self.assertEqual(evidence['units']['value'], 'mm')

    def test_mapping_missing_tokens_and_string_ids(self):
        rows, evidence = self.load()
        self.assertEqual(rows[0], {'sample_id': '001', 'sample_key': '{"id": "001"}', 'group': 'A',
                                   'group_raw': 'A', 'value': '3', 'value_raw': '3'})
        self.assertEqual((rows[1]['value'], rows[1]['value_raw']), ('', 'NA'))
        self.assertEqual(evidence['sha256'], adapter.digest(self.data))

    def test_missing_file_never_falls_back(self):
        self.data.unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'BLOCKED'):
            self.load()

    def test_hash_change_blocks(self):
        self.data.write_text(self.data.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            self.load()

    def test_schema_change_blocks(self):
        config = copy.deepcopy(self.config)
        config['columns']['value'] = 'absent'
        with self.assertRaisesRegex(ValueError, 'mapped columns'):
            self.load(config)

    def test_unknown_unit_and_paper_source_block(self):
        for config in (dict(self.config, units={}), dict(self.config, role='paper_reproduction')):
            with self.assertRaises(ValueError):
                self.load(config)

    def test_duplicate_ids_and_wrong_count_block(self):
        self.data.write_text('id,condition,length\n001,A,1\n001,A,2\n')
        self.config['sha256'] = adapter.digest(self.data)
        with self.assertRaisesRegex(ValueError, 'duplicate sample'):
            self.load()
        self.data.write_text('id,condition,length\n001,A,1\n')
        self.config['sha256'] = adapter.digest(self.data)
        with self.assertRaisesRegex(ValueError, 'record count'):
            self.load()

    def test_generated_ids_need_explicit_policy(self):
        config = copy.deepcopy(self.config)
        config['columns']['sample_id'] = None
        with self.assertRaisesRegex(ValueError, 'id_policy'):
            self.load(config)
        config['id_policy'] = 'source_row_number'
        rows, _ = self.load(config)
        self.assertEqual(rows[0]['sample_id'], 'row:1')

    def test_default_production_entry_is_blocked(self):
        with self.assertRaisesRegex(ValueError, 'BLOCKED'):
            adapter.load_input(ASSETS / 'input_config.json')

    def test_repeated_measurements_use_joint_keys(self):
        self.data.write_text('id,time,condition,length\n1,0,A,1\n1,1,A,2\n')
        config = dict(self.config, sha256=adapter.digest(self.data), key_columns=['id', 'time'])
        rows, evidence = self.load(config)
        self.assertEqual([row['sample_id'] for row in rows], ['1', '1'])
        self.assertEqual(rows[1]['sample_key'], '{"id": "1", "time": "1"}')
        self.assertEqual((evidence['rows'], evidence['units_identified']), (2, 1))
        with self.assertRaisesRegex(ValueError, 'configure key_columns'):
            self.load(dict(config, key_columns=None))
        self.data.write_text('id,time,condition,length\n1,0,A,1\n1,0,A,2\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.load(dict(config, sha256=adapter.digest(self.data)))
        for keys in ([], ['time'], ['id', 'id'], ['id', 'length'], 'id'):
            with self.assertRaisesRegex(ValueError, 'key_columns'):
                self.load(dict(config, key_columns=keys))
        with self.assertRaisesRegex(ValueError, 'mapped columns'):
            self.load(dict(config, sha256=adapter.digest(self.data), key_columns=['id', 'absent']))

    def test_all_configuration_gaps_reported_together(self):
        with self.assertRaises(ValueError) as caught:
            adapter.load_input(ASSETS / 'input_config.json')
        for text in ('dataset_id', 'configure source', 'source_type', 'role', 'sha256', 'units.value', 'file missing'):
            self.assertIn(text, str(caught.exception))

    def test_unreadable_inputs_are_blocked(self):
        self.data.write_bytes('id,condition,length\n1,对照,3\n'.encode('gbk'))
        config = dict(self.config, sha256=adapter.digest(self.data), expected_rows=1)
        with self.assertRaisesRegex(ValueError, 'BLOCKED: cannot decode'):
            self.load(config)
        self.assertEqual(self.load(dict(config, encoding='gb18030'))[0][0]['group'], '对照')
        (self.root / 'config.json').write_text('{')
        with self.assertRaisesRegex(ValueError, 'BLOCKED.*not valid JSON'):
            adapter.load_input(self.root / 'config.json')

    def test_records_do_not_expose_local_directories(self):
        _, evidence = self.load()
        self.assertEqual(evidence['path'], 'observations.csv')
        nested = self.root / 'nested'
        nested.mkdir()
        (nested / 'config.json').write_text(json.dumps(dict(self.config, path=str(self.data))))
        _, evidence = adapter.load_input(nested / 'config.json')
        self.assertEqual(evidence['path'], '<external>/observations.csv')
        self.assertNotIn(str(self.root), json.dumps(evidence))

    def test_init_drafts_facts_but_still_blocks(self):
        path = self.root / 'draft.json'
        config = adapter.draft_config(self.data, path)
        self.assertEqual((config['sha256'], config['expected_rows']), (adapter.digest(self.data), 2))
        self.assertEqual((config['path'], config['available_columns']), ('observations.csv', ['id', 'condition', 'length']))
        with self.assertRaisesRegex(ValueError, 'BLOCKED') as caught:
            adapter.load_input(path)
        for text in ('missing_values', 'role', 'source', 'units.value'):
            self.assertIn(text, str(caught.exception))
        with self.assertRaisesRegex(ValueError, 'already configured'):
            adapter.draft_config(self.data, path)
        template = self.root / 'input_config.json'
        template.write_bytes((ASSETS / 'input_config.json').read_bytes())
        adapter.draft_config(self.data, template)
