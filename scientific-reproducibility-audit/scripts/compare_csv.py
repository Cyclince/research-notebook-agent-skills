#!/usr/bin/env python3
"""Compare scalar CSV outputs by explicit keys, using only the standard library."""
import argparse
import csv
from decimal import Decimal, InvalidOperation, localcontext
import math
from pathlib import Path

FIELDS = [
    "schema_version", "dataset_id", "source_code_version", "refactor_code_version",
    "method", "check_type", "sample_key", "metric", "old_value", "new_value",
    "abs_diff", "rel_diff", "atol", "rtol", "comparison_rule", "qc_before",
    "qc_after", "status", "notes",
]


def read_table(path, keys):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        if not columns or any(not name.strip() for name in columns) or len(columns) != len(set(columns)):
            raise ValueError(f"{path}: missing or duplicate column names")
        if not set(keys) <= set(columns):
            raise ValueError(f"{path}: required key columns absent")
        rows = {}
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}:{line}: malformed CSV row")
            key = tuple(row[column] for column in keys)
            if any(not value.strip() for value in key):
                raise ValueError(f"{path}:{line}: empty key")
            if key in rows:
                raise ValueError(f"{path}:{line}: duplicate key {key!r}")
            rows[key] = row
    return columns, rows


def compare(old, new, *, keys, numeric=(), qc=(), atol=0.0, rtol=0.0,
            dataset_id="", method="", source_code_version="", refactor_code_version=""):
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("specify unique key columns")
    if not all(math.isfinite(value) and value >= 0 for value in (atol, rtol)):
        raise ValueError("atol and rtol must be finite and nonnegative")
    if set(keys) & (set(numeric) | set(qc)) or set(numeric) & set(qc):
        raise ValueError("key, numeric and QC columns must not overlap")
    metadata = dict(schema_version="1.0", dataset_id=dataset_id, method=method,
                    source_code_version=source_code_version,
                    refactor_code_version=refactor_code_version)
    report = []

    def record(check_type, sample_key, metric, old_value, new_value, status, **extra):
        row = dict.fromkeys(FIELDS, "")
        row.update(metadata, check_type=check_type, sample_key=sample_key, metric=metric,
                   old_value=old_value, new_value=new_value, status=status, **extra)
        report.append(row)

    try:
        old_columns, old_rows = read_table(old, keys)
        new_columns, new_rows = read_table(new, keys)
    except ValueError as error:
        record("structure", "", "table", "", "", "FAIL", notes=str(error))
        return report
    all_columns = set(old_columns) | set(new_columns)
    if not (set(numeric) | set(qc)) <= all_columns:
        raise ValueError("unknown numeric or QC column")
    if not old_rows or not new_rows:
        record("structure", "", "nonempty", len(old_rows), len(new_rows), "FAIL",
               notes="Empty outputs require a method-specific non-applicability decision.")
    for column in sorted(all_columns):
        if column not in old_columns or column not in new_columns:
            record("structure", "", column, column in old_columns, column in new_columns,
                   "FAIL", notes="Column set changed")
    import json
    for key in sorted(set(old_rows) | set(new_rows)):
        label = json.dumps(dict(zip(keys, key)), ensure_ascii=False, sort_keys=True)
        if key not in old_rows or key not in new_rows:
            record("structure", label, "row", key in old_rows, key in new_rows,
                   "FAIL", notes="Key set changed")
            continue
        for column in sorted((set(old_columns) & set(new_columns)) - set(keys)):
            before, after = old_rows[key][column], new_rows[key][column]
            if column in numeric:
                # Only blank and case-insensitive NaN are missing numeric values.
                # Other tokens require a documented normalization before comparison.
                missing_before = before.strip().lower() in ("", "nan")
                missing_after = after.strip().lower() in ("", "nan")
                if missing_before or missing_after:
                    record("numeric", label, column, before, after,
                           "PASS" if missing_before == missing_after else "FAIL",
                           comparison_rule="same missing mask", atol=atol, rtol=rtol)
                    continue
                try:
                    a, b = Decimal(before), Decimal(after)
                    if not a.is_finite() or not b.is_finite():
                        raise ValueError("nonfinite numeric value")
                    # Preserve CSV precision, including integers beyond float64's exact range.
                    tolerance_a, tolerance_r = Decimal(str(atol)), Decimal(str(rtol))
                    numbers = (a, b, tolerance_a, tolerance_r)
                    precision = max(n.adjusted() for n in numbers) - min(n.as_tuple().exponent for n in numbers) + 30
                    if precision > 10000 or any(abs(n.adjusted()) > 10000 for n in numbers):
                        raise ValueError("numeric range exceeds comparison precision limit")
                    with localcontext() as context:
                        context.prec = max(50, precision)
                        difference = abs(b - a)
                        limit = tolerance_a + tolerance_r * abs(a)
                        passed = difference <= limit
                        record("numeric", label, column, before, after, "PASS" if passed else "FAIL",
                               abs_diff=difference, rel_diff=difference / abs(a) if a else "",
                               atol=atol, rtol=rtol,
                               comparison_rule="abs_diff <= atol + rtol * abs(old_value)")
                except (ValueError, InvalidOperation):
                    record("numeric", label, column, before, after, "FAIL",
                           notes="Invalid, infinite or out-of-range numeric value")
            else:
                extra = dict(qc_before=before, qc_after=after) if column in qc else {}
                record("qc" if column in qc else "field", label, column, before, after,
                       "PASS" if before == after else "FAIL", comparison_rule="exact string", **extra)
    record("structure", "", "row_count", len(old_rows), len(new_rows),
           "PASS" if set(old_rows) == set(new_rows) else "FAIL", comparison_rule="identical key sets")
    return report


def write_report(path, rows):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--keys", nargs="+", required=True)
    parser.add_argument("--numeric", nargs="*", default=[])
    parser.add_argument("--qc", nargs="*", default=[])
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    for flag in ("dataset-id", "method", "source-code-version", "refactor-code-version"):
        parser.add_argument("--" + flag, default="")
    parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    output, old, new = args.pop("output"), args.pop("old"), args.pop("new")
    if output.resolve() in (old.resolve(), new.resolve()):
        parser.error("report output must not overwrite either input")
    try:
        rows = compare(old, new, **args)
    except (OSError, ValueError, UnicodeError) as error:
        row = dict.fromkeys(FIELDS, "")
        row.update(schema_version="1.0", check_type="execution", status="BLOCKED", notes=str(error))
        write_report(output, [row])
        print(f"BLOCKED: {error}")
        return 2
    write_report(output, rows)
    failed = sum(row["status"] == "FAIL" for row in rows)
    print(f"{len(rows)} checks; {failed} FAIL; report: {output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
