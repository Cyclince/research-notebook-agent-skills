#!/usr/bin/env python3
"""Run the R template cell by cell with Rscript and compare it with the Python example.

Needs R with jsonlite and digest. Cells run in separate processes for the redraw checks,
which is stricter than a shared kernel. Jupyter itself (IRkernel) is not exercised here.
"""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import nbformat

from smoke_notebook import ASSETS, ROOT, execute

NAME = "notebook_template_r.ipynb"
sys.path.insert(0, str(ROOT / "scientific-reproducibility-audit/scripts"))
import compare_csv


def run(directory, cells, message=None):
    script = directory / "cells.R"
    script.write_text("\n\n".join(cell.source for cell in cells), encoding="utf-8")
    result = subprocess.run(["Rscript", "--vanilla", "--encoding=UTF-8", script.name], cwd=directory,
                            capture_output=True, text=True, encoding="utf-8")
    script.unlink()
    if message is None:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and message in result.stderr, (message, result.stderr)


def statuses(directory):
    with (directory / "example_output_r/validation_matrix.csv").open(encoding="utf-8") as stream:
        return {row["metric"]: row["status"] for row in csv.DictReader(stream)}


def main():
    if not shutil.which("Rscript"):
        print("BLOCKED: Rscript not found; the R template was not verified")
        return 2
    if subprocess.run(["Rscript", "-e", "library(jsonlite); library(digest)"], capture_output=True).returncode:
        print("BLOCKED: R packages jsonlite and digest are required; the R template was not verified")
        return 2
    with tempfile.TemporaryDirectory(prefix="research-notebook-r-") as temporary:
        directory = Path(temporary).resolve() / "assets"
        shutil.copytree(ASSETS, directory)
        notebook = nbformat.read(directory / NAME, as_version=4)

        def code(tag=None):
            return [c for c in notebook.cells if c.cell_type == "code" and (tag is None or tag in c.metadata.tags)]

        run(directory, code(), "BLOCKED")
        for cell in notebook.cells:
            cell.source = cell.source.replace('"input_config.json"', '"penguins_input.json"')
        nbformat.write(notebook, directory / NAME)
        run(directory, code())
        status = statuses(directory)
        assert all(status[m] == "NOT-RUN" for m in ("execution:source-match", "figure:visual-check", "figure:no-glyph-warning"))
        assert "FAIL" not in status.values() and status["input:identity"] == "PASS"
        # Both languages must agree through the shipped comparison tool.
        execute(nbformat.read(directory / "real_data_example.ipynb", as_version=4), directory)
        for name, key, numeric in (("group_summary.csv", "group", ["n", "n_units", "mean", "sd"]),
                                   ("observations_for_plot.csv", "sample_id", ["value"])):
            rows = compare_csv.compare(directory / "example_output" / name, directory / "example_output_r" / name,
                                       keys=[key], numeric=numeric, rtol=1e-12)
            assert all(row["status"] == "PASS" for row in rows), [r for r in rows if r["status"] != "PASS"][:3]
        run(directory, code("plot"))
        for name, message in (("example_output_r/group_summary.csv", "Result changed"), ("data/penguins.csv", "Input changed"),
                              ("penguins_input.json", "Input config changed"), ("notebook_provenance.R", "Science code changed")):
            path = directory / name
            original = path.read_bytes()
            path.write_bytes(original + b"\n")
            run(directory, code("plot"), message)
            path.write_bytes(original)
        assert statuses(directory)["provenance:code"] == "FAIL"
        data = directory / "data/penguins.csv"
        data.rename(directory / "data/away.csv")
        run(directory, code("plot"))
        assert statuses(directory)["input:identity"] == "BLOCKED"

        # Literal NA-like groups, quoting, repeated measurements, and a single declared token.
        data = directory / "data/measurements.csv"
        data.write_text('id,time,g,v\n1,0,None,1\n1,1,None,2\n2,0,NULL,3\n3,0,"dr,ug",4\n4,0,"dr,ug",<0.05\n'
                        '5,0,"dr,ug",NA\n6,0,"dr,ug","1,5"\n7,0,x,inf\n8,0,,1\n9,0,x,\n', encoding="utf-8")
        config = json.loads((directory / "penguins_input.json").read_text(encoding="utf-8"))
        config.update(path="data/measurements.csv", sha256=hashlib.sha256(data.read_bytes()).hexdigest(), expected_rows=10,
                      columns={"sample_id": "id", "group": "g", "value": "v"}, key_columns=["id", "time"], missing_values=["NA"])
        (directory / "penguins_input.json").write_text(json.dumps(config), encoding="utf-8")
        run(directory, code())
        execute(nbformat.read(directory / "real_data_example.ipynb", as_version=4), directory)
        for name, key, numeric in (("group_summary.csv", "group", ["n", "n_units", "mean", "sd"]),
                                   ("excluded_records.csv", "sample_key", [])):
            rows = compare_csv.compare(directory / "example_output" / name, directory / "example_output_r" / name,
                                       keys=[key], numeric=numeric, rtol=1e-12)
            assert all(row["status"] == "PASS" for row in rows), [r for r in rows if r["status"] != "PASS"][:3]
        tiff = [cell.copy() for cell in code("plot")]
        tiff[0].source = tiff[0].source.replace('FORMAT <- "png"', 'FORMAT <- "tiff"')
        cairo = subprocess.run(["Rscript", "--vanilla", "-e", 'f <- tempfile(); tiff(f, type="cairo"); plot(1); dev.off(); q(status = !file.exists(f))'],
                               capture_output=True, cwd=directory).returncode == 0
        run(directory, tiff, None if cairo else "BLOCKED")
        if cairo:
            from PIL import Image
            with Image.open(directory / "example_output_r/group_mean_example.tiff") as image:
                assert image.info["compression"] == "tiff_lzw"
    print("PASS: R template - blocking, Run All, redraw, rejection, QC reasons and agreement with Python")
    print(f"{'PASS' if cairo else 'NOT-RUN'}: R LZW TIFF" + ("" if cairo else " (cairo unavailable; refused as BLOCKED)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
