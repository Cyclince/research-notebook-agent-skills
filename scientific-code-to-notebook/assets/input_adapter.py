"""Explicit CSV/TSV input contract. No data download or synthetic fallback."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

SOURCE_TYPES = ('user_data', 'paper_data', 'public_observations')
ROLES = ('paper_reproduction', 'method_transfer', 'input_example')
MAPPED = ('sample_id', 'group', 'value')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_config(config_path):
    try:
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    except ValueError as error:
        raise ValueError(f'BLOCKED: {Path(config_path).name} is not valid JSON ({error})') from error
    if not isinstance(config, dict):
        raise ValueError(f'BLOCKED: {Path(config_path).name} must contain a JSON object')
    return config


def resolve_input(config_path, config=None):
    """Return the data path; relative paths are relative to the config file."""
    config_path = Path(config_path).resolve()
    path = Path((config or read_config(config_path))['path']).expanduser()
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def portable_path(path, root):
    """Path to record: relative inside root, otherwise only the name (no local directories)."""
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return f'<external>/{Path(path).name}'


def config_problems(config):
    """Return every configuration gap, so that they can be fixed in one pass."""
    problems = []
    for key in ('dataset_id', 'path', 'source', 'source_type', 'role', 'sha256', 'columns', 'units', 'missing_values'):
        if config.get(key) in ('', None):
            problems.append(f'configure {key}')
    if config.get('dataset_id') == 'YOUR_DATASET_VERSION':
        problems.append('replace the placeholder dataset_id')
    if config.get('source_type') and config['source_type'] not in SOURCE_TYPES:
        problems.append(f'source_type must identify a real data source: {", ".join(SOURCE_TYPES)}')
    if config.get('role') and config['role'] not in ROLES:
        problems.append(f'role must be one of: {", ".join(ROLES)}')
    if config.get('role') == 'paper_reproduction' and not config.get('paper_reference'):
        problems.append('paper_reproduction requires a paper_reference')
    units = config.get('units')
    if units not in ('', None) and (not isinstance(units, dict) or not units.get('value')):
        problems.append('specify units.value (use dimensionless explicitly)')
    missing = config.get('missing_values')
    if missing not in ('', None) and not (isinstance(missing, list) and all(isinstance(x, str) for x in missing)):
        problems.append('missing_values must be an explicit list of strings')
    if config.get('delimiter', ',') not in (',', '\t'):
        problems.append('delimiter must be comma or tab; otherwise implement a format-specific reader')
    mapping = config.get('columns')
    if mapping not in ('', None):
        if not isinstance(mapping, dict) or not set(MAPPED) <= set(mapping):
            problems.append('map sample_id, group and value in columns')
        else:
            for name in ('group', 'value'):
                if not mapping[name]:
                    problems.append(f'map columns.{name}')
            names = [mapping[x] for x in MAPPED if mapping[x]]
            if len(names) != len(set(names)):
                problems.append('mapped columns missing or overlapping')
            keys = config.get('key_columns')
            if not mapping['sample_id'] and config.get('id_policy') != 'source_row_number':
                problems.append('missing ID requires an explicit id_policy')
            if keys is not None:
                if not isinstance(keys, list) or not keys or len(keys) != len(set(keys)):
                    problems.append('key_columns must be a nonempty list of unique column names')
                elif not mapping['sample_id'] or mapping['sample_id'] not in keys:
                    problems.append('key_columns must include the mapped sample_id column')
                elif mapping['value'] in keys:
                    problems.append('key_columns must not include the value column')
    return problems


def load_input(config_path):
    """Return (rows, provenance).

    Each row has sample_id, sample_key (JSON of the unique key), group, value and the
    untouched group_raw/value_raw. Declared missing tokens become '' in group/value only.
    sample_id identifies the experimental unit and may repeat when key_columns is configured.
    """
    config_path = Path(config_path).resolve()
    config = read_config(config_path)
    problems = config_problems(config)
    path = resolve_input(config_path, config) if config.get('path') else None
    if path and not path.is_file():
        message = f'input file missing: {config["path"]}; configure a real input, no simulated fallback'
        if not problems:
            raise FileNotFoundError(f'BLOCKED: {message}')
        problems.append(message)
    if problems:
        raise ValueError(f'BLOCKED: {config_path.name}\n' + '\n'.join(f'  - {x}' for x in problems))
    actual_hash = digest(path)
    if actual_hash != config['sha256']:
        raise ValueError('BLOCKED: input SHA-256 changed; verify dataset version before updating config')
    delimiter = config.get('delimiter', '\t' if path.suffix.lower() == '.tsv' else ',')
    mapping, missing = config['columns'], config['missing_values']
    keys = config.get('key_columns') or ([mapping['sample_id']] if mapping['sample_id'] else [])
    encoding = config.get('encoding', 'utf-8-sig')
    try:
        with path.open(encoding=encoding, newline='') as stream:
            reader = csv.DictReader(stream, delimiter=delimiter)
            fields = reader.fieldnames
            if not fields or len(fields) != len(set(fields)) or any(not x.strip() for x in fields):
                raise ValueError('BLOCKED: missing or duplicate headers')
            needed = {mapping[x] for x in MAPPED if mapping[x]} | set(keys)
            if not needed <= set(fields):
                raise ValueError(f'BLOCKED: mapped columns missing or overlapping: {sorted(needed - set(fields))}')
            rows, seen = [], set()
            for index, record in enumerate(reader, 1):
                if None in record or any(v is None for v in record.values()):
                    raise ValueError(f'BLOCKED: malformed record {index}')
                identifier = record[mapping['sample_id']] if mapping['sample_id'] else f'row:{index}'
                key = {name: record[name] for name in keys} or {'source_row': str(index)}
                if any(not x.strip() for x in key.values()):
                    raise ValueError(f'BLOCKED: blank sample ID or key at record {index}')
                sample_key = json.dumps(key, ensure_ascii=False, sort_keys=True)
                if sample_key in seen:
                    raise ValueError(f'BLOCKED: duplicate sample ID or key at record {index}: {sample_key}; '
                                     'for repeated measurements configure key_columns')
                seen.add(sample_key)
                row = {'sample_id': identifier, 'sample_key': sample_key}
                for name in ('group', 'value'):
                    # Preserve strings and ID leading zeros; only normalize declared missing tokens.
                    raw = record[mapping[name]]
                    row[name], row[name + '_raw'] = '' if raw in missing else raw, raw
                rows.append(row)
    except (UnicodeError, LookupError) as error:
        raise ValueError(f'BLOCKED: cannot decode input as {encoding}; set encoding explicitly') from error
    except csv.Error as error:
        raise ValueError(f'BLOCKED: input is not readable as delimited text ({error})') from error
    if not rows or (config.get('expected_rows') is not None and len(rows) != config['expected_rows']):
        raise ValueError('BLOCKED: empty input or unexpected record count')
    provenance = {key: config.get(key) for key in ('dataset_id', 'source', 'source_type', 'role', 'paper_reference', 'units', 'columns', 'missing_values', 'id_policy')}
    # Local absolute directories stay in the config and out of shared records.
    provenance.update(path=portable_path(path, config_path.parent), sha256=actual_hash, rows=len(rows),
                      units_identified=len({row['sample_id'] for row in rows}), key_columns=keys,
                      config_file=config_path.name, config_sha256=digest(config_path),
                      adapter_sha256=digest(__file__))
    return rows, provenance


def draft_config(data_path, config_path, encoding='utf-8-sig'):
    """Record only observable facts; scientific choices stay blank, so the draft still blocks."""
    data_path, config_path = Path(data_path).expanduser().resolve(), Path(config_path).resolve()
    if config_path.exists():
        existing = read_config(config_path)
        if existing.get('sha256') or existing.get('source'):
            raise ValueError(f'BLOCKED: {config_path.name} is already configured; not overwritten')
    delimiter = '\t' if data_path.suffix.lower() == '.tsv' else ','
    try:
        with data_path.open(encoding=encoding, newline='') as stream:
            reader = csv.reader(stream, delimiter=delimiter)
            header = next(reader, [])
            count = sum(1 for row in reader if row)
    except (UnicodeError, LookupError) as error:
        raise ValueError(f'BLOCKED: cannot decode input as {encoding}; pass --encoding') from error
    except csv.Error as error:
        raise ValueError(f'BLOCKED: input is not readable as delimited text ({error})') from error
    if not header:
        raise ValueError('BLOCKED: input has no header')
    try:
        path = data_path.relative_to(config_path.parent).as_posix()
    except ValueError:
        path = str(data_path)
    config = {
        'dataset_id': '', 'path': path, 'source': '', 'source_type': '', 'role': '', 'paper_reference': '',
        'sha256': digest(data_path), 'sha256_origin': 'computed_locally; compare with the published checksum if one exists',
        'expected_rows': count, 'columns': {'sample_id': '', 'group': '', 'value': ''},
        'key_columns': None, 'units': {'value': ''}, 'missing_values': None,
        'encoding': encoding, 'delimiter': delimiter, 'available_columns': header}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--init', type=Path, metavar='DATA', help='Draft an unconfigured config from a real CSV/TSV')
    parser.add_argument('--encoding', default='utf-8-sig', help='Only with --init')
    args = parser.parse_args()
    try:
        if args.init:
            config = draft_config(args.init, args.config, args.encoding)
            print(f'Drafted {args.config}. Still BLOCKED until configured:')
            print('\n'.join(f'  - {x}' for x in config_problems(config)))
            return 0
        rows, provenance = load_input(args.config)
    except (ValueError, OSError, KeyError, TypeError) as error:
        message = str(error)
        print(message if message.startswith('BLOCKED') else f'BLOCKED: {message}')
        return 2
    print(json.dumps({'status': 'PASS', 'records': len(rows), 'provenance': provenance}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
