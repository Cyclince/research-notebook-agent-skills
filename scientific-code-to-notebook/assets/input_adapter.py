"""Explicit CSV/TSV input contract. No data download or synthetic fallback."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_input(config_path):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    for key in ('dataset_id', 'path', 'source', 'source_type', 'role', 'sha256', 'columns', 'units', 'missing_values'):
        if key not in config or config[key] in ('', None):
            raise ValueError(f'BLOCKED: configure {key} in {config_path.name}')
    if config['source_type'] not in ('user_data', 'paper_data', 'public_observations'):
        raise ValueError('BLOCKED: production input must identify a real data source')
    if config['role'] not in ('paper_reproduction', 'method_transfer', 'input_example'):
        raise ValueError('BLOCKED: specify the scientific role of the dataset')
    if config['role'] == 'paper_reproduction' and not config.get('paper_reference'):
        raise ValueError('BLOCKED: paper reproduction requires a paper_reference')
    if not isinstance(config['units'], dict) or not config['units'].get('value'):
        raise ValueError('BLOCKED: specify the value unit (use dimensionless explicitly)')
    if not isinstance(config['missing_values'], list):
        raise ValueError('BLOCKED: missing_values must be an explicit list')
    path = Path(config['path']).expanduser()
    path = (config_path.parent / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f'BLOCKED: input file missing: {path}; configure a real input, no simulated fallback')
    actual_hash = digest(path)
    if actual_hash != config['sha256']:
        raise ValueError('BLOCKED: input SHA-256 changed; verify dataset version before updating config')
    delimiter = config.get('delimiter', '\t' if path.suffix.lower() == '.tsv' else ',')
    if delimiter not in (',', '\t'):
        raise ValueError('Use a CSV/TSV adapter or implement an explicit format-specific reader')
    mapping = config['columns']
    if not isinstance(mapping, dict) or not {'sample_id', 'group', 'value'} <= set(mapping):
        raise ValueError('BLOCKED: map sample_id, group and value columns')
    if not mapping['sample_id'] and config.get('id_policy') != 'source_row_number':
        raise ValueError('BLOCKED: missing ID requires an explicit id_policy')
    with path.open(encoding=config.get('encoding', 'utf-8-sig'), newline='') as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)) or any(not x.strip() for x in fields):
            raise ValueError('BLOCKED: missing or duplicate headers')
        needed = [mapping[x] for x in ('sample_id', 'group', 'value') if mapping[x]]
        if len(needed) != len(set(needed)) or not set(needed) <= set(fields):
            raise ValueError('BLOCKED: mapped columns missing or overlapping')
        rows, ids = [], set()
        for index, record in enumerate(reader, 1):
            if None in record or any(v is None for v in record.values()):
                raise ValueError(f'BLOCKED: malformed record {index}')
            identifier = record[mapping['sample_id']] if mapping['sample_id'] else f'row:{index}'
            if not identifier.strip() or identifier in ids:
                raise ValueError(f'BLOCKED: blank or duplicate sample ID at record {index}')
            ids.add(identifier)
            row = {key: record[mapping[key]] for key in ('group', 'value')}
            # Preserve strings and ID leading zeros; only normalize declared missing tokens.
            row = {key: '' if value in config['missing_values'] else value for key, value in row.items()}
            rows.append(dict(sample_id=identifier, **row))
    if not rows or (config.get('expected_rows') is not None and len(rows) != config['expected_rows']):
        raise ValueError('BLOCKED: empty input or unexpected record count')
    provenance = {key: config.get(key) for key in ('dataset_id', 'source', 'source_type', 'role', 'paper_reference', 'units', 'columns', 'missing_values', 'id_policy')}
    provenance.update(path=str(path), sha256=actual_hash, rows=len(rows),
                      config_path=str(config_path), config_sha256=digest(config_path),
                      adapter_sha256=digest(__file__))
    return rows, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args()
    try:
        rows, provenance = load_input(args.config)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error))
        return 2
    print(json.dumps({'status': 'PASS', 'records': len(rows), 'provenance': provenance}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
