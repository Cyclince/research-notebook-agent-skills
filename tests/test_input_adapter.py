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
        self.assertEqual(rows[0], {'sample_id': '001', 'group': 'A', 'value': '3'})
        self.assertEqual(rows[1]['value'], '')
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
