#!/usr/bin/env python3
"""Validate skill metadata, bundled links and standalone contract consistency."""
import ast
import csv
import importlib.util
import re
from pathlib import Path

import nbformat
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted(ROOT.glob("*/SKILL.md"))
assert len(SKILLS) == 3, "Expected three standalone skills"
contracts, headers = [], []
for path in SKILLS:
    text = path.read_text(encoding="utf-8")
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == path.parent.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"])
    assert 0 < len(metadata["description"]) <= 1024
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if "://" not in link:
            assert (path.parent / link).exists(), (path, link)
    for link in re.findall(r"`((?:references|assets|scripts)/[^`\s]+)`", text):
        assert (path.parent / link).exists(), (path, link)
    contracts.append((path.parent / "references/result-contract.md").read_bytes())
    with (path.parent / "assets/validation_matrix_template.csv").open() as stream:
        headers.append(next(csv.reader(stream)))
assert contracts.count(contracts[0]) == len(contracts), "Contract copies drifted"
assert headers.count(headers[0]) == len(headers), "Validation schema copies drifted"
script = ROOT / "scientific-reproducibility-audit/scripts/compare_csv.py"
spec = importlib.util.spec_from_file_location("compare_csv", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert headers[0] == module.FIELDS
for path in ROOT.rglob("*.ipynb"):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(cell.source)
            assert not cell.outputs and cell.execution_count is None, "Commit clean templates only"
for path in ROOT.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"))
print("PASS: metadata, links, standalone contracts, schema, notebook and Python syntax")
