"""Provenance and acceptance bookkeeping for the notebook templates.

Contains no scientific computation, data selection or plotting. Checks raise explicitly
instead of using assert, so they still hold under PYTHONOPTIMIZE / python -O.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

FIELDS = ("schema_version,dataset_id,source_code_version,refactor_code_version,method,check_type,"
          "sample_key,metric,old_value,new_value,abs_diff,rel_diff,atol,rtol,comparison_rule,"
          "qc_before,qc_after,status,notes").split(",")


class CheckFailed(RuntimeError):
    pass


def require(condition, message):
    if not bool(condition):
        raise CheckFailed(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_text(path, text):
    """Replace atomically, so an interrupted run cannot leave half a record."""
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def write_json(path, value):
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


# ---- code identity -------------------------------------------------------------------

def _normalize(source):
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def notebook_sources(path):
    """Return (calculation, plot) code sources. Untagged code counts as calculation."""
    path = Path(path)
    require(path.is_file(), f"Notebook file {path} not found: set NOTEBOOK_FILE to the current file name "
                            "and use the notebook directory as working directory")
    calculation, plot = [], []
    for cell in json.loads(path.read_text(encoding="utf-8"))["cells"]:
        source = _normalize("".join(cell["source"]))
        if cell["cell_type"] == "code" and source:
            (plot if "plot" in cell.get("metadata", {}).get("tags", []) else calculation).append(source)
    return calculation, plot


def sources_hash(sources):
    return hashlib.sha256(json.dumps(sources, ensure_ascii=False).encode()).hexdigest()


def science_hash(path):
    return sources_hash(notebook_sources(path)[0])


def executed_sources():
    """Sources executed by this kernel, or None outside IPython."""
    try:
        shell = get_ipython()  # noqa: F821 - provided by IPython
    except NameError:
        try:
            from IPython import get_ipython as find
        except ImportError:
            return None
        shell = find()
    if shell is None:
        return None
    return [x for x in map(_normalize, shell.history_manager.input_hist_raw) if x]


def check_execution(path):
    """Require that the executed calculation cells are exactly the saved ones, in order.

    Call from the cell that saves results. Plot cells in between are ignored.
    """
    calculation, plot = notebook_sources(path)
    history = executed_sources()
    if history is None:
        return {"source_match": None, "clean_kernel": None}
    advice = ("Executed code differs from the saved notebook: save the notebook, restart the kernel "
              "and Run All before saving results")
    require(calculation and calculation[0] in history, advice)
    start = len(history) - 1 - history[::-1].index(calculation[0])
    run = [x for x in history[start:] if x not in plot]
    require(run == calculation[:len(run)], advice)
    return {"source_match": True, "clean_kernel": start == 0}


def local_code(root="."):
    """Hash imported modules that belong to the project, so editing src/ invalidates results."""
    root = Path(root).resolve()
    prefix = Path(sys.prefix).resolve()
    found = {}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if not name:
            continue
        path = Path(name).resolve()
        if (not path.is_file() or root not in path.parents or {"site-packages", "dist-packages"} & set(path.parts)
                or (root in prefix.parents and prefix in path.parents)):
            continue
        found[path.relative_to(root).as_posix()] = sha256(path)
    return dict(sorted(found.items()))


def changed_code(recorded, root="."):
    return [name for name, value in recorded.items()
            if not (Path(root) / name).is_file() or sha256(Path(root) / name) != value]


# ---- acceptance matrix ---------------------------------------------------------------

class Checks:
    """Rows of one validation_matrix.csv; a status is only set by an evaluated condition.

    Every expected metric starts as NOT-RUN, so an aborted run cannot keep older PASS rows.
    Existing rows for other metrics, methods or datasets are preserved.
    """

    def __init__(self, path, *, dataset_id, method, refactor_code_version, expected=(),
                 source_code_version="unknown"):
        self.path = Path(path)
        self.base = dict(schema_version="1.0", dataset_id=dataset_id, method=method,
                         source_code_version=source_code_version,
                         refactor_code_version=refactor_code_version)
        self.rows = {}
        for metric in expected:
            self.set(metric, "NOT-RUN")
        self.save()

    def set(self, metric, status, notes="", rule=""):
        kind = metric.split(":")[0]
        row = dict.fromkeys(FIELDS, "")
        # input:* rows keep their prefix in metric and use the contract's check types.
        row.update(self.base, metric=metric, status=status, notes=notes, comparison_rule=rule,
                   check_type={"input:qc": "qc", "input:schema": "structure"}.get(
                       metric, "provenance" if kind == "input" else kind))
        self.rows[metric] = row

    def check(self, metric, condition, message, rule=""):
        ok = bool(condition)
        self.set(metric, "PASS" if ok else "FAIL", "" if ok else message, rule or message)
        if not ok:
            self.save()
            raise CheckFailed(message)

    def save(self):
        def identity(row):
            return tuple(row[x] for x in ("dataset_id", "method", "check_type", "sample_key", "metric"))
        current = {identity(row) for row in self.rows.values()}
        kept = []
        if self.path.is_file():
            with self.path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                require(reader.fieldnames == FIELDS, f"{self.path} does not use the validation_matrix schema")
                kept = [row for row in reader if identity(row) not in current]
        temporary = Path(str(self.path) + ".tmp")
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(kept + list(self.rows.values()))
        os.replace(temporary, self.path)
