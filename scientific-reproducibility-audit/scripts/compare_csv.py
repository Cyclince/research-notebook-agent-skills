#!/usr/bin/env python3
"""Compare scalar CSV outputs by explicit keys, using only the standard library."""
import argparse
import csv
from decimal import Decimal, localcontext
import json
import math
from pathlib import Path
import re

FIELDS = [
    "schema_version", "dataset_id", "source_code_version", "refactor_code_version",
    "method", "check_type", "sample_key", "metric", "old_value", "new_value",
    "abs_diff", "rel_diff", "atol", "rtol", "comparison_rule", "qc_before",
    "qc_after", "status", "notes",
]
RULE = "abs_diff <= atol + rtol * abs(old_value)"
# Plain decimal/scientific notation only: Decimal() alone also accepts "1_000" and full-width digits.
NUMBER = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
csv.field_size_limit(16 * 1024 * 1024)


class UnreadableInput(Exception):
    """The table cannot be read at all, so nothing was compared (BLOCKED, not FAIL)."""


def read_table(path, keys, encoding="utf-8-sig", delimiter=","):
    try:
        with Path(path).open(newline="", encoding=encoding) as stream:
            reader = csv.DictReader(stream, delimiter=delimiter)
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
    except (UnicodeError, LookupError) as error:
        raise UnreadableInput(f"{path}: cannot decode as {encoding}; pass --encoding ({error})") from error
    except csv.Error as error:
        raise UnreadableInput(f"{path}: not readable as CSV ({error})") from error
    return columns, rows


def compare(old, new, *, keys, numeric=(), qc=(), atol=0.0, rtol=0.0, tolerances=None,
            missing_values=(), encoding="utf-8-sig", delimiter=",",
            dataset_id="unknown", method="unknown", source_code_version="unknown",
            refactor_code_version="unknown", sink=None):
    """Return one row per check. A sink callable receives rows instead (constant memory).

    tolerances maps column -> (atol, rtol) and overrides the defaults; its columns are numeric.
    missing_values are caller-declared tokens treated as missing in numeric columns,
    in addition to blank and NaN. They are never applied to keys, QC or text fields.
    """
    tolerances = dict(tolerances or {})
    numeric = set(numeric) | set(tolerances)
    if not keys or len(keys) != len(set(keys)):
        raise ValueError("specify unique key columns")
    for pair in [(atol, rtol), *tolerances.values()]:
        if len(pair) != 2 or not all(math.isfinite(value) and value >= 0 for value in pair):
            raise ValueError("atol and rtol must be finite and nonnegative")
    if set(keys) & (numeric | set(qc)) or numeric & set(qc):
        raise ValueError("key, numeric and QC columns must not overlap")
    declared = {token.strip() for token in missing_values}
    if any(NUMBER.fullmatch(token) for token in declared):
        raise ValueError("a numeric literal cannot be declared as a missing value")
    missing_rule = "same missing mask" + (f"; declared missing: {sorted(declared)}" if declared else "")
    metadata = dict(schema_version="1.0", dataset_id=dataset_id, method=method,
                    source_code_version=source_code_version,
                    refactor_code_version=refactor_code_version)
    report = []
    emit = sink or report.append

    def record(check_type, sample_key, metric, old_value, new_value, status, **extra):
        row = dict.fromkeys(FIELDS, "")
        row.update(metadata, check_type=check_type, sample_key=sample_key, metric=metric,
                   old_value=old_value, new_value=new_value, status=status, **extra)
        emit(row)

    def is_missing(text):
        text = text.strip()
        return text.lower() in ("", "nan") or text in declared

    try:
        old_columns, old_rows = read_table(old, keys, encoding, delimiter)
        new_columns, new_rows = read_table(new, keys, encoding, delimiter)
    except ValueError as error:
        record("structure", "", "table", "", "", "FAIL", notes=str(error))
        return report
    all_columns = set(old_columns) | set(new_columns)
    if not (numeric | set(qc)) <= all_columns:
        raise ValueError(f"unknown numeric or QC column: {sorted((numeric | set(qc)) - all_columns)}")
    if not old_rows or not new_rows:
        record("structure", "", "nonempty", len(old_rows), len(new_rows), "FAIL",
               notes="Empty outputs require a method-specific non-applicability decision.")
    for column in sorted(all_columns):
        if column not in old_columns or column not in new_columns:
            record("structure", "", column, column in old_columns, column in new_columns,
                   "FAIL", notes="Column set changed")
    shared = sorted((set(old_columns) & set(new_columns)) - set(keys))
    for key in sorted(set(old_rows) | set(new_rows)):
        label = json.dumps(dict(zip(keys, key)), ensure_ascii=False, sort_keys=True)
        if key not in old_rows or key not in new_rows:
            record("structure", label, "row", key in old_rows, key in new_rows,
                   "FAIL", notes="Key set changed")
            continue
        for column in shared:
            before, after = old_rows[key][column], new_rows[key][column]
            if column in numeric:
                limit_a, limit_r = tolerances.get(column, (atol, rtol))
                missing_before, missing_after = is_missing(before), is_missing(after)
                if missing_before or missing_after:
                    record("numeric", label, column, before, after,
                           "PASS" if missing_before == missing_after else "FAIL",
                           comparison_rule=missing_rule, atol=limit_a, rtol=limit_r)
                    continue
                try:
                    if not all(NUMBER.fullmatch(text.strip()) for text in (before, after)):
                        raise ValueError("not a finite plain number")
                    a, b = Decimal(before.strip()), Decimal(after.strip())
                    # Preserve CSV precision, including integers beyond float64's exact range.
                    tolerance_a, tolerance_r = Decimal(str(limit_a)), Decimal(str(limit_r))
                    numbers = (a, b, tolerance_a, tolerance_r)
                    precision = max(n.adjusted() for n in numbers) - min(n.as_tuple().exponent for n in numbers) + 30
                    if precision > 10000 or any(abs(n.adjusted()) > 10000 for n in numbers):
                        raise ValueError("numeric range exceeds comparison precision limit")
                    with localcontext() as context:
                        context.prec = max(50, precision)
                        difference = abs(b - a)
                        passed = difference <= tolerance_a + tolerance_r * abs(a)
                        record("numeric", label, column, before, after, "PASS" if passed else "FAIL",
                               abs_diff=difference, rel_diff=difference / abs(a) if a else "",
                               atol=limit_a, rtol=limit_r, comparison_rule=RULE)
                except (ValueError, ArithmeticError):
                    record("numeric", label, column, before, after, "FAIL",
                           atol=limit_a, rtol=limit_r, comparison_rule=RULE,
                           notes="Invalid, infinite or out-of-range numeric value")
            else:
                extra = dict(qc_before=before, qc_after=after) if column in qc else {}
                record("qc" if column in qc else "field", label, column, before, after,
                       "PASS" if before == after else "FAIL", comparison_rule="exact string", **extra)
    record("structure", "", "row_count", len(old_rows), len(new_rows),
           "PASS" if set(old_rows) == set(new_rows) else "FAIL", comparison_rule="identical key sets")
    return report


class Summary:
    """Aggregate per field; keep every non-PASS row as evidence."""

    def __init__(self):
        self.groups, self.details, self.checks, self.failed = {}, [], 0, 0

    def add(self, row):
        self.checks += 1
        self.failed += row["status"] == "FAIL"
        if row["check_type"] == "structure":
            self.details.append(row)
            return
        group = self.groups.setdefault((row["check_type"], row["metric"]),
                                       dict(first=row, n=0, fail=0, finite=0, abs=None, rel=None))
        group["n"] += 1
        if row["status"] == "FAIL":
            group["fail"] += 1
            self.details.append(row)
        if row["abs_diff"] != "":
            group["finite"] += 1
            group["abs"] = max(row["abs_diff"], group["abs"] or 0)
        if row["rel_diff"] != "":
            group["rel"] = max(row["rel_diff"], group["rel"] or 0)

    def rows(self):
        result = []
        for (check_type, metric), group in sorted(self.groups.items()):
            notes = f"summary: compared={group['n']}; fail={group['fail']}"
            if check_type == "numeric":
                notes += f"; finite_pairs={group['finite']}; abs_diff and rel_diff are maxima"
                if not group["finite"]:
                    notes += "; no finite value was compared"
            row = dict.fromkeys(FIELDS, "")
            row.update({key: group["first"][key] for key in FIELDS[:5]}, check_type=check_type,
                       metric=metric, atol=group["first"]["atol"], rtol=group["first"]["rtol"],
                       comparison_rule=RULE if check_type == "numeric" else "exact string",
                       abs_diff="" if group["abs"] is None else f"{group['abs']:.6g}",
                       rel_diff="" if group["rel"] is None else f"{group['rel']:.6g}",
                       status="FAIL" if group["fail"] else "PASS", notes=notes)
            result.append(row)
        return result + self.details


def write_report(path, rows, append=False):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a" if append else "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not append:
            writer.writeheader()
        writer.writerows(rows)


def check_destination(path, overwrite, append):
    """Return whether to append; raise if the report would destroy an existing file."""
    path = Path(path)
    if not path.exists():
        return False
    if append:
        content = path.read_bytes()
        with path.open(newline="", encoding="utf-8-sig") as stream:
            header = next(csv.reader(stream), None)
        if header != FIELDS:
            raise ValueError(f"cannot append: {path} does not use the validation_matrix schema")
        if not content.endswith(b"\n"):
            raise ValueError(f"cannot append: {path} does not end with a newline")
        return True
    if not overwrite:
        raise ValueError(f"{path} exists; choose --append, --overwrite or another path")
    return False


def parse_tolerance(text):
    """COLUMN=ATOL,RTOL"""
    column, separator, pair = text.rpartition("=")
    try:
        atol, rtol = (float(value) for value in pair.split(","))
    except ValueError:
        separator = ""
    if not separator or not column:
        raise argparse.ArgumentTypeError(f"expected COLUMN=ATOL,RTOL, got {text!r}")
    return column, (atol, rtol)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--keys", nargs="+", required=True)
    parser.add_argument("--numeric", nargs="*", default=[], help="Columns using the default --atol/--rtol")
    parser.add_argument("--tol", nargs="+", action="extend", type=parse_tolerance, default=[],
                        metavar="COLUMN=ATOL,RTOL", help="Per-column tolerance; implies numeric")
    parser.add_argument("--qc", nargs="*", default=[])
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--missing-values", nargs="*", default=[], metavar="TOKEN",
                        help="Extra missing tokens in numeric columns, for example NA from R")
    parser.add_argument("--encoding", default="utf-8-sig", help="For example gb18030")
    parser.add_argument("--delimiter", default=",", help="One character, or 'tab'")
    for flag in ("dataset-id", "method", "source-code-version", "refactor-code-version"):
        parser.add_argument("--" + flag, default="unknown")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full", action="store_true", help="Write every check instead of summaries plus failures")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--append", action="store_true", help="Add rows to an existing validation matrix")
    group.add_argument("--overwrite", action="store_true", help="Replace an existing report")
    args = vars(parser.parse_args())
    output, old, new, full = (args.pop(name) for name in ("output", "old", "new", "full"))
    overwrite, append = args.pop("overwrite"), args.pop("append")
    if output.resolve() in (old.resolve(), new.resolve()):
        parser.error("report output must not overwrite either input")
    tolerances = args.pop("tol")
    if len(dict(tolerances)) != len(tolerances):
        parser.error("duplicate column in --tol")
    args["tolerances"] = dict(tolerances)
    args["delimiter"] = "\t" if args["delimiter"] == "tab" else args["delimiter"]
    if len(args["delimiter"]) != 1:
        parser.error("delimiter must be one character")
    try:
        append = check_destination(output, overwrite, append)
    except (OSError, ValueError, csv.Error) as error:
        print(f"BLOCKED: {error}")
        return 2
    summary, everything = Summary(), []

    def sink(row):
        summary.add(row)
        if full:
            everything.append(row)

    try:
        compare(old, new, sink=sink, **args)
    except (OSError, ValueError, UnreadableInput) as error:
        row = dict.fromkeys(FIELDS, "")
        row.update(schema_version="1.0", check_type="execution", metric="compare_csv",
                   dataset_id=args["dataset_id"], method=args["method"],
                   source_code_version=args["source_code_version"],
                   refactor_code_version=args["refactor_code_version"],
                   status="BLOCKED", notes=str(error))
        write_report(output, [row], append)
        print(f"BLOCKED: {error}")
        return 2
    aggregated = summary.rows()
    write_report(output, everything if full else aggregated, append)
    for row in aggregated:
        if not row["sample_key"] and row["notes"].startswith("summary:"):
            print(f"{row['status']:5} {row['check_type']}:{row['metric']} max_abs_diff={row['abs_diff'] or '-'} {row['notes']}")
    unknown = [name for name in ("dataset_id", "method", "source_code_version", "refactor_code_version")
               if args[name] == "unknown"]
    if unknown:
        print(f"NOTE: {', '.join(unknown)} recorded as unknown; this is not a complete acceptance")
    print(f"{summary.checks} checks; {summary.failed} FAIL; report: {output}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
