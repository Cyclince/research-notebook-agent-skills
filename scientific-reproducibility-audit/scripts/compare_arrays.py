#!/usr/bin/env python3
"""Compare array outputs (.npy, .npz, NetCDF) variable by variable.

Requires numpy; NetCDF additionally requires netCDF4. Arrays are never broadcast,
transposed, regridded or reindexed. Object arrays are refused rather than unpickled.
"""
import argparse
import csv
import math
from pathlib import Path

import numpy as np

from compare_csv import FIELDS, check_destination, parse_tolerance, write_report

RULE = "elementwise abs_diff <= atol + rtol * abs(old_value); same missing mask"
# Attributes that change the meaning of stored numbers.
ATTRIBUTES = ("units", "calendar", "scale_factor", "add_offset", "_FillValue", "missing_value")


class UnreadableInput(Exception):
    """The file cannot be read, so nothing was compared (BLOCKED, not FAIL)."""


def read_arrays(path):
    """Return {name: (array, dimensions, attributes)}; masked entries stay masked."""
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".npy":
            return {"array": (np.load(path, allow_pickle=False), None, {})}
        if suffix == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                return {name: (archive[name], None, {}) for name in archive.files}
        if suffix in (".nc", ".nc4", ".cdf"):
            try:
                import netCDF4
            except ImportError as error:
                raise UnreadableInput("netCDF4 is not installed; NetCDF was not compared") from error
            result = {}

            def visit(group, prefix):
                for name, variable in group.variables.items():
                    attributes = {key: str(variable.getncattr(key)) for key in ATTRIBUTES if key in variable.ncattrs()}
                    result[prefix + name] = (variable[...], variable.dimensions, attributes)
                for name, child in group.groups.items():
                    visit(child, f"{prefix}{name}/")

            with netCDF4.Dataset(path) as dataset:
                visit(dataset, "")
            return result
    except UnreadableInput:
        raise
    except (OSError, ValueError, EOFError, RuntimeError, KeyError) as error:
        raise UnreadableInput(f"{path}: {error}") from error
    raise UnreadableInput(f"{path}: unsupported format {suffix!r}; use a format-specific reader")


def missing_mask(array):
    mask = np.ma.getmaskarray(array).copy()
    data = np.ma.getdata(array)
    if data.dtype.kind in "fc":
        mask |= np.isnan(data)
    elif data.dtype.kind in "mM":
        mask |= np.isnat(data)
    return mask


def absolute_difference(a, b):
    """Exact for equal integer dtypes; float64 (or wider) otherwise."""
    if a.dtype == b.dtype and a.dtype.kind in "iu":
        high, low = np.maximum(a, b), np.minimum(a, b)
        return high.astype(np.uint64) - low.astype(np.uint64)
    wide = np.result_type(a.dtype, b.dtype, np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        return np.abs(b.astype(wide) - a.astype(wide))


def compare(old, new, *, atol=0.0, rtol=0.0, tolerances=None, dataset_id="unknown",
            method="unknown", source_code_version="unknown", refactor_code_version="unknown"):
    tolerances = dict(tolerances or {})
    for pair in [(atol, rtol), *tolerances.values()]:
        if not all(math.isfinite(value) and value >= 0 for value in pair):
            raise ValueError("atol and rtol must be finite and nonnegative")
    before, after = read_arrays(old), read_arrays(new)
    names = sorted(set(before) | set(after))
    unknown = set(tolerances) - set(names)
    if unknown:
        raise ValueError(f"unknown variable in tolerances: {sorted(unknown)}")
    report = []

    def record(check_type, metric, old_value, new_value, ok, **extra):
        row = dict.fromkeys(FIELDS, "")
        row.update(schema_version="1.0", dataset_id=dataset_id, method=method,
                   source_code_version=source_code_version, refactor_code_version=refactor_code_version,
                   check_type=check_type, metric=metric, old_value=old_value, new_value=new_value,
                   status="PASS" if ok else "FAIL", **extra)
        report.append(row)

    if not names:
        record("structure", "nonempty", 0, 0, False, notes="No variables found")
    for name in names:
        if name not in before or name not in after:
            record("structure", name, name in before, name in after, False, notes="Variable set changed")
            continue
        (a, dims_a, attrs_a), (b, dims_b, attrs_b) = before[name], after[name]
        for label, x, y in (("shape", a.shape, b.shape), ("dtype", str(a.dtype), str(b.dtype)),
                            ("dimensions", dims_a, dims_b), ("attributes", attrs_a, attrs_b)):
            if x or y:
                record("structure", f"{name}:{label}", str(x), str(y), x == y, comparison_rule="exact")
        if a.shape != b.shape:
            record("numeric", name, "", "", False, notes="Not compared elementwise: shapes differ")
            continue
        if a.size == 0:
            record("structure", f"{name}:nonempty", 0, 0, False,
                   notes="Empty outputs require a method-specific non-applicability decision.")
            continue
        mask_a, mask_b = missing_mask(a), missing_mask(b)
        changed = int((mask_a != mask_b).sum())
        record("qc", f"{name}:missing-mask", int(mask_a.sum()), int(mask_b.sum()), changed == 0,
               comparison_rule="identical missing mask", notes=f"positions changed={changed}")
        valid = ~(mask_a | mask_b)
        if not valid.any():
            record("numeric", name, "", "", changed == 0, notes="no finite value was compared")
            continue
        x, y = np.ma.getdata(a)[valid], np.ma.getdata(b)[valid]
        index = np.argwhere(valid)
        if x.dtype.kind not in "iufc" or y.dtype.kind not in "iufc":
            different = np.asarray(x != y)
            first = f"; first at {tuple(int(i) for i in index[different.argmax()])}" if different.any() else ""
            record("field", name, "", "", not different.any(), comparison_rule="exact",
                   notes=f"compared={x.size}; fail={int(different.sum())}{first}")
            continue
        infinite = int((~np.isfinite(x)).sum() + (~np.isfinite(y)).sum())
        limit_a, limit_r = tolerances.get(name, (atol, rtol))
        difference = absolute_difference(x, y)
        with np.errstate(over="ignore", invalid="ignore"):
            magnitude = np.abs(x.astype(np.result_type(x.dtype, np.float64)))
            passed = difference <= limit_a + limit_r * magnitude
            relative = np.divide(difference, magnitude, out=np.zeros(x.shape), where=magnitude > 0)
        usable = (magnitude > 0) & np.isfinite(relative)
        passed &= np.isfinite(x) & np.isfinite(y)
        worst = int(np.argmax(np.where(np.isnan(difference), np.inf, difference)))
        record("numeric", name, str(x[worst]), str(y[worst]), bool(passed.all()),
               abs_diff=str(difference[worst]), rel_diff=f"{relative[usable].max():.6g}" if usable.any() else "",
               atol=limit_a, rtol=limit_r, comparison_rule=RULE,
               notes=f"compared={x.size}; fail={int((~passed).sum())}; infinite={infinite}; "
                     f"values shown at largest abs_diff, index {tuple(int(i) for i in index[worst])}; rel_diff is the maximum")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--atol", type=float, default=0.0)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--tol", nargs="+", action="extend", type=parse_tolerance, default=[],
                        metavar="VARIABLE=ATOL,RTOL")
    for flag in ("dataset-id", "method", "source-code-version", "refactor-code-version"):
        parser.add_argument("--" + flag, default="unknown")
    parser.add_argument("--output", type=Path, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--append", action="store_true")
    group.add_argument("--overwrite", action="store_true")
    args = vars(parser.parse_args())
    output, old, new = (args.pop(name) for name in ("output", "old", "new"))
    overwrite, append = args.pop("overwrite"), args.pop("append")
    if output.resolve() in (old.resolve(), new.resolve()):
        parser.error("report output must not overwrite either input")
    args["tolerances"] = dict(args.pop("tol"))
    try:
        append = check_destination(output, overwrite, append)
    except (OSError, ValueError, csv.Error) as error:
        print(f"BLOCKED: {error}")
        return 2
    try:
        rows = compare(old, new, **args)
    except (OSError, ValueError, UnreadableInput) as error:
        row = dict.fromkeys(FIELDS, "")
        row.update(schema_version="1.0", check_type="execution", metric="compare_arrays",
                   **{key: args[key] for key in ("dataset_id", "method", "source_code_version", "refactor_code_version")},
                   status="BLOCKED", notes=str(error))
        write_report(output, [row], append)
        print(f"BLOCKED: {error}")
        return 2
    write_report(output, rows, append)
    failed = [row for row in rows if row["status"] == "FAIL"]
    for row in failed:
        print(f"FAIL  {row['check_type']}:{row['metric']} {row['notes']}")
    print(f"{len(rows)} checks; {len(failed)} FAIL; report: {output}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
