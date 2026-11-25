#!/usr/bin/env python3
"""Exercise Run All, clean-kernel redraw, QC and stale-result rejection in isolation."""
import argparse
from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scientific-code-to-notebook/assets"
NAME = "real_data_example.ipynb"
OUT = "example_output"


def execute(notebook, directory, **environment):
    # The default python3 kernelspec resolves this interpreter via PATH.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["MPLCONFIGDIR"] = str(directory / ".matplotlib")
    os.environ["IPYTHONDIR"] = str(directory / ".ipython")
    os.environ["JUPYTER_RUNTIME_DIR"] = str(directory / ".jupyter-runtime")
    os.environ.update(environment)
    try:
        return NotebookClient(deepcopy(notebook), timeout=120, kernel_name="python3",
                              resources={"metadata": {"path": str(directory)}}).execute()
    finally:
        for key in environment:
            del os.environ[key]


def expect_failure(notebook, directory, message, **environment):
    try:
        execute(notebook, directory, **environment)
    except CellExecutionError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError(f"Expected rejection: {message}")


def plot_only(notebook):
    cells = [cell for cell in notebook.cells if "plot" in cell.metadata.get("tags", [])]
    return nbformat.v4.new_notebook(cells=deepcopy(cells), metadata=deepcopy(notebook.metadata))


def replaced(notebook, index, before, after):
    result = deepcopy(notebook)
    assert before in result.cells[index].source, before
    result.cells[index].source = result.cells[index].source.replace(before, after)
    return result


def statuses(directory):
    with (directory / OUT / "validation_matrix.csv").open(encoding="utf-8") as stream:
        return {row["metric"]: row["status"] for row in csv.DictReader(stream)}


def record(directory):
    return json.loads((directory / OUT / "provenance.json").read_text(encoding="utf-8"))


def check_default_flow(root):
    """Run All, then style-only redraw in new kernels, then rejection of every changed identity."""
    directory = root / "default"
    shutil.copytree(ASSETS, directory)
    template = nbformat.read(directory / NAME, as_version=4)
    nbformat.write(execute(template, directory), directory / "executed.ipynb")
    (directory / "executed.ipynb").rename(root / "executed.ipynb")
    result = directory / OUT / "group_summary.csv"
    original, calculation = result.read_bytes(), record(directory)["calculation"]
    summary = pd.read_csv(result)
    assert int(summary["n"].sum()) == 342 and set(summary["group"]) == {"Adelie", "Chinstrap", "Gentoo"}
    excluded = pd.read_csv(directory / OUT / "excluded_records.csv")
    assert list(excluded["qc_reason"]) == ["declared_missing"] * 2
    status = statuses(directory)
    manual = {"input:preview", "figure:visual-check"}
    assert {k for k, v in status.items() if v == "NOT-RUN"} == manual
    assert all(v == "PASS" for k, v in status.items() if k not in manual), status
    # Shared records must not expose local directories; one record and one matrix only.
    assert str(root) not in (directory / OUT / "provenance.json").read_text(encoding="utf-8")
    assert {p.name for p in (directory / OUT).iterdir()} == {
        "group_summary.csv", "observations_for_plot.csv", "excluded_records.csv", "provenance.json",
        "validation_matrix.csv", "group_mean_example.png"}

    redraw = plot_only(template)
    execute(replaced(redraw, 0, 'COLOR = "#4878A8"', 'COLOR = "#C65D3B"'), directory)
    assert result.read_bytes() == original and record(directory)["calculation"] == calculation
    assert record(directory)["figures"]["group_mean_example"]["style"]["color"] == "#C65D3B"
    for extension in ("tif", "pdf"):
        execute(replaced(redraw, 0, 'FORMAT = "png"', f'FORMAT = "{extension}"'), directory)
        path = directory / OUT / f"group_mean_example.{extension}"
        if extension == "tif":
            with Image.open(path) as image:
                assert (image.format, image.mode, image.info["compression"]) == ("TIFF", "RGB", "tiff_lzw")
        assert path.stat().st_size > 0
        path.unlink()
    expect_failure(replaced(redraw, 0, "TITLE = \"", "TITLE = \"" + "long " * 60), directory, "exceed the canvas")
    assert statuses(directory)["figure:within-canvas"] == "FAIL"

    result.write_bytes(original.replace(b"38.79", b"58.79"))
    for environment in ({}, {"PYTHONOPTIMIZE": "1"}):
        expect_failure(redraw, directory, "Result changed", **environment)
        status = statuses(directory)
        assert status["provenance:result"] == "FAIL", "An aborted redraw must not keep old PASS rows"
        assert status["figure:nonempty"] == status["figure:data-rows"] == "NOT-RUN"
    result.write_bytes(original)
    for name, message in (("data/penguins.csv", "Input changed"), ("penguins_input.json", "Input config changed"),
                          ("input_adapter.py", "Science code changed")):
        path = directory / name
        path.write_bytes(path.read_bytes() + b"\n")
        expect_failure(redraw, directory, message)
        shutil.copy2(ASSETS / name, path)
    expect_failure(replaced(redraw, 0, '"ddof": 1', '"ddof": 0'), directory, "Science parameters changed")
    nbformat.write(replaced(template, 2, 'METHOD = "group-summary"', 'METHOD = "group-summary"  # edited'), directory / NAME)
    expect_failure(redraw, directory, "Science code changed")
    shutil.copy2(ASSETS / NAME, directory / NAME)

    # Moving the project keeps the checks; a missing input is BLOCKED, never PASS.
    moved = root / "moved"
    shutil.move(directory, moved)
    execute(redraw, moved)
    assert statuses(moved)["input:identity"] == "PASS"
    (moved / "data/penguins.csv").write_text("tampered")
    expect_failure(redraw, moved, "Input changed")
    (moved / "data/penguins.csv").unlink()
    execute(redraw, moved)
    assert statuses(moved)["input:identity"] == "BLOCKED"
    assert record(moved)["figures"]["group_mean_example"]["input_revalidated"] is False
    # The production template must block without a configured real dataset.
    expect_failure(nbformat.read(moved / "notebook_template.ipynb", as_version=4), moved, "BLOCKED")


def check_executed_code(root):
    """Results are only saved when the kernel ran exactly the saved calculation cells."""
    directory = root / "executed-code"
    shutil.copytree(ASSETS, directory)
    template = nbformat.read(directory / NAME, as_version=4)
    expect_failure(replaced(template, 6, '"mean"), sd', '"median"), sd'), directory, "differs from the saved notebook")
    assert not (directory / OUT / "group_summary.csv").exists()
    stale = deepcopy(template)
    stale.cells.insert(5, nbformat.v4.new_code_cell("valid['value'] *= 1000"))
    expect_failure(stale, directory, "differs from the saved notebook")
    # Saved but untagged calculation code is part of the fingerprint.
    nbformat.write(stale, directory / NAME)
    execute(stale, directory)
    nbformat.write(replaced(stale, 5, "1000", "7"), directory / NAME)
    expect_failure(plot_only(template), directory, "Science code changed")
    # Re-running everything in one kernel is allowed but is not a clean-kernel PASS.
    nbformat.write(template, directory / NAME)
    twice = deepcopy(template)
    twice.cells = deepcopy(template.cells[:7]) + deepcopy(template.cells[:7])
    for cell in twice.cells:
        cell.id = nbformat.v4.new_code_cell().id
    execute(twice, directory)
    assert statuses(directory)["execution:source-match"] == "PASS"
    assert statuses(directory)["execution:clean-kernel"] == "NOT-RUN"
    (directory / NAME).rename(directory / "renamed.ipynb")
    expect_failure(template, directory, "set NOTEBOOK_FILE")


def check_awkward_input(root):
    """Literal group names, distinct QC reasons and repeated measurements."""
    directory = root / "awkward"
    shutil.copytree(ASSETS, directory)
    data = directory / "data/measurements.csv"
    data.write_text('id,time,g,v\n1,0,None,1\n1,1,None,2\n2,0,null,3\n3,0,drug,4\n4,0,drug,<0.05\n'
                    '5,0,drug,NA\n6,0,drug,"1,5"\n7,0,drug,inf\n8,0,,1\n9,0,drug,\n', encoding="utf-8")
    config = json.loads((directory / "penguins_input.json").read_text(encoding="utf-8"))
    config.update(path="data/measurements.csv", sha256=hashlib.sha256(data.read_bytes()).hexdigest(), expected_rows=10,
                  columns={"sample_id": "id", "group": "g", "value": "v"}, key_columns=["id", "time"], missing_values=["NA"])
    (directory / "penguins_input.json").write_text(json.dumps(config), encoding="utf-8")
    execute(nbformat.read(directory / NAME, as_version=4), directory)
    summary = pd.read_csv(directory / OUT / "group_summary.csv", keep_default_na=False).set_index("group")
    assert list(summary.index) == ["None", "drug", "null"]
    assert (summary.loc["None", "n"], summary.loc["None", "n_units"]) == (2, 1)
    excluded = pd.read_csv(directory / OUT / "excluded_records.csv", keep_default_na=False, dtype=str)
    assert dict(zip(excluded["sample_id"], excluded["qc_reason"])) == {
        "4": "unparseable_value", "5": "declared_missing", "6": "unparseable_value",
        "7": "nonfinite_value", "8": "empty_group", "9": "undeclared_blank"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New directory for inspectable QA artifacts")
    args = parser.parse_args()
    context = None
    if args.output_dir:
        directory = args.output_dir.resolve()
        directory.mkdir(parents=True, exist_ok=False)
    else:
        context = tempfile.TemporaryDirectory(prefix="research-notebook-qa-")
        directory = Path(context.name).resolve()
    try:
        for check in (check_default_flow, check_executed_code, check_awkward_input):
            check(directory)
            print(f"PASS: {check.__name__} - {check.__doc__}", flush=True)
        if not context:
            print(f"QA artifacts: {directory}")
    finally:
        if context:
            context.cleanup()


if __name__ == "__main__":
    main()
