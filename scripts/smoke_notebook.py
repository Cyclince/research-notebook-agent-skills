#!/usr/bin/env python3
"""Exercise Run All, clean-kernel redraw, QC and stale-result rejection in isolation."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scientific-code-to-notebook/assets"


def execute(notebook, directory):
    # The default python3 kernelspec resolves this interpreter via PATH.
    os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", "")
    os.environ["MPLBACKEND"] = "Agg"
    os.environ["MPLCONFIGDIR"] = str(directory / ".matplotlib")
    os.environ["IPYTHONDIR"] = str(directory / ".ipython")
    os.environ["JUPYTER_RUNTIME_DIR"] = str(directory / ".jupyter-runtime")
    return NotebookClient(notebook, timeout=120, kernel_name="python3",
                          resources={"metadata": {"path": str(directory)}}).execute()


def expect_failure(notebook, directory, message):
    try:
        execute(notebook, directory)
    except CellExecutionError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError(f"Expected rejection: {message}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="New directory for inspectable QA artifacts")
    args = parser.parse_args()
    if args.output_dir:
        directory = args.output_dir.resolve()
        directory.mkdir(parents=True, exist_ok=False)
        context = None
    else:
        context = tempfile.TemporaryDirectory(prefix="research-notebook-qa-")
        directory = Path(context.name)
    try:
        shutil.copytree(ASSETS, directory, dirs_exist_ok=True)
        for path in directory.rglob("__pycache__"):
            shutil.rmtree(path)
        template = nbformat.read(directory / "real_data_example.ipynb", as_version=4)
        executed = execute(deepcopy(template), directory)
        nbformat.write(executed, directory / "executed.ipynb")
        result = directory / "example_output/group_summary.csv"
        original_result = result.read_bytes()
        manifest = directory / "example_output/provenance.json"
        original_manifest = manifest.read_bytes()
        plot_cells = [cell for cell in template.cells if "plot" in cell.metadata.get("tags", [])]
        redraw = nbformat.v4.new_notebook(cells=deepcopy(plot_cells), metadata=deepcopy(template.metadata))
        # New kernel with only plot cells; style changes must not touch calculation artifacts.
        redraw.cells[0].source = redraw.cells[0].source.replace('COLOR = "#4878A8"', 'COLOR = "#C65D3B"')
        execute(redraw, directory)
        assert result.read_bytes() == original_result
        assert manifest.read_bytes() == original_manifest
        style = json.loads((directory / "example_output/figure_parameters.json").read_text())
        assert style["color"] == "#C65D3B"
        assert all((directory / f"example_output/group_mean_example.{ext}").stat().st_size > 0
                   for ext in ("svg", "pdf", "png"))
        result.write_bytes(original_result + b"\n")
        expect_failure(redraw, directory, "Result changed")
        result.write_bytes(original_result)
        source = directory / "data/penguins.csv"
        source.write_bytes(source.read_bytes() + b"\n")
        expect_failure(redraw, directory, "Input changed")
        shutil.copy2(ASSETS / "data/penguins.csv", source)
        changed_parameters = deepcopy(redraw)
        changed_parameters.cells[0].source = changed_parameters.cells[0].source.replace('"ddof": 1', '"ddof": 0')
        expect_failure(changed_parameters, directory, "Science parameters changed")
        changed_source = deepcopy(template)
        changed_source.cells[2].source += "\n# changed scientific implementation\n"
        nbformat.write(changed_source, directory / "real_data_example.ipynb")
        expect_failure(redraw, directory, "Science code changed")
        shutil.copy2(ASSETS / "real_data_example.ipynb", directory / "real_data_example.ipynb")
        # Production template must block without a configured real dataset.
        production = nbformat.read(directory / "notebook_template.ipynb", as_version=4)
        expect_failure(production, directory, "BLOCKED")
        import pandas as pd
        summary = pd.read_csv(result)
        assert int(summary["n"].sum()) == 342
        assert set(summary["group"]) == {"Adelie", "Chinstrap", "Gentoo"}
        excluded = pd.read_csv(directory / "example_output/excluded_records.csv")
        assert len(excluded) == 2
        # Restore default fixture and redraw for the artifact retained for visual inspection.
        shutil.copy2(ASSETS / "data/penguins.csv", source)
        execute(deepcopy(template), directory)
        print("PASS: Run All, clean-kernel redraw, style-only change, result/input/parameter/code rejection, real observed input/QC and unconfigured production rejection")
        print(f"QA artifacts: {directory}")
    finally:
        if context:
            context.cleanup()


if __name__ == "__main__":
    main()
