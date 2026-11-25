import csv
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scientific-reproducibility-audit/scripts/compare_csv.py"
spec = importlib.util.spec_from_file_location("compare_csv", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def table(self, name, rows, fields=("id", "value", "qc")):
        path = self.root / name
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(fields)
            writer.writerows(rows)
        return path

    def run_comparison(self, before, after, **kwargs):
        return module.compare(before, after, keys=["id"], numeric=["value"], qc=["qc"], **kwargs)

    def test_row_order_does_not_change_results(self):
        rows = [("001", "1", "ok"), ("002", "2", "ok")]
        result = self.run_comparison(self.table("a", rows), self.table("b", rows[::-1]))
        self.assertTrue(all(row["status"] == "PASS" for row in result))
        self.assertIn('"001"', result[0]["sample_key"])

    def test_leading_zero_ids_are_distinct(self):
        result = self.run_comparison(self.table("a", [("001", "1", "ok")]),
                                     self.table("b", [("1", "1", "ok")]))
        self.assertTrue(any(row["status"] == "FAIL" for row in result))

    def test_duplicate_keys_fail(self):
        before = self.table("a", [("a", "1", "ok")] * 2)
        result = self.run_comparison(before, self.table("b", [("a", "1", "ok")]))
        self.assertEqual(result[0]["status"], "FAIL")
        self.assertIn("duplicate key", result[0]["notes"])

    def test_missing_rows_fail_even_when_shared_values_match(self):
        result = self.run_comparison(self.table("a", [("a", "1", "ok"), ("b", "2", "ok")]),
                                     self.table("b", [("a", "1", "ok")]))
        self.assertTrue(any(row["metric"] == "row" and row["status"] == "FAIL" for row in result))

    def test_qc_changes_fail(self):
        result = self.run_comparison(self.table("a", [("a", "1", "ok")]),
                                     self.table("b", [("a", "1", "invalid")]))
        self.assertTrue(any(row["check_type"] == "qc" and row["status"] == "FAIL" for row in result))

    def test_missing_masks_compared_before_numeric_values(self):
        before = self.table("a", [("a", "NaN", "missing")])
        same = self.run_comparison(before, self.table("b", [("a", "", "missing")]))
        changed = self.run_comparison(before, self.table("c", [("a", "0", "missing")]))
        self.assertTrue(all(row["status"] == "PASS" for row in same))
        self.assertTrue(any(row["status"] == "FAIL" for row in changed))

    def test_nonfinite_or_invalid_values_fail(self):
        for value in ("Inf", "-inf", "NA", "nonsense"):
            with self.subTest(value=value):
                result = self.run_comparison(self.table("a", [("a", value, "ok")]),
                                             self.table("b", [("a", value, "ok")]))
                self.assertTrue(any(row["status"] == "FAIL" for row in result))

    def test_zero_reference_uses_absolute_tolerance(self):
        before = self.table("a", [("a", "0", "ok")])
        after = self.table("b", [("a", "0.01", "ok")])
        result = self.run_comparison(before, after, atol=0.02)
        numeric = next(row for row in result if row["check_type"] == "numeric")
        self.assertEqual(numeric["status"], "PASS")
        self.assertEqual(numeric["rel_diff"], "")
        self.assertTrue(any(row["status"] == "FAIL" for row in self.run_comparison(before, after)))

    def test_large_magnitude_difference_compared_without_overflow(self):
        result = self.run_comparison(self.table("a", [("a", "-1e308", "ok")]),
                                     self.table("b", [("a", "1e308", "ok")]), rtol=1)
        self.assertTrue(any(row["status"] == "FAIL" for row in result))

    def test_integer_precision_is_not_lost_to_float_conversion(self):
        result = self.run_comparison(self.table("a", [("a", "9007199254740992", "ok")]),
                                     self.table("b", [("a", "9007199254740993", "ok")]))
        numeric = next(row for row in result if row["check_type"] == "numeric")
        self.assertEqual(numeric["status"], "FAIL")
        self.assertEqual(numeric["abs_diff"], 1)

    def test_invalid_tolerances_rejected(self):
        for tolerance in (-1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                self.run_comparison("a", "b", atol=tolerance)

    def test_empty_tables_fail(self):
        result = self.run_comparison(self.table("a", []), self.table("b", []))
        self.assertTrue(any(row["status"] == "FAIL" for row in result))

    def test_changed_fields_fail(self):
        before = self.table("a", [("a", "1", "ok", "x")], ("id", "value", "qc", "extra"))
        result = self.run_comparison(before, self.table("b", [("a", "1", "ok")]))
        self.assertTrue(any(row["metric"] == "extra" and row["status"] == "FAIL" for row in result))

    def test_empty_key_and_malformed_rows_fail(self):
        for rows in ([ ("", "1", "ok") ], [ ("a", "1") ]):
            result = self.run_comparison(self.table("a", rows), self.table("b", [("a", "1", "ok")]))
            self.assertEqual(result[0]["status"], "FAIL")

    def test_joint_keys_are_supported(self):
        a = self.table("a", [("a", "t1", "1"), ("a", "t2", "2")], ("id", "time", "value"))
        result = module.compare(a, a, keys=["id", "time"], numeric=["value"])
        self.assertTrue(all(row["status"] == "PASS" for row in result))

    def test_cli_exit_codes_and_report_schema(self):
        a = self.table("a", [("a", "1", "ok")])
        b = self.table("b", [("a", "2", "ok")])
        output = self.root / "report.csv"
        base = [sys.executable, str(SCRIPT), str(a), str(b), "--keys", "id", "--numeric", "value", "--overwrite", "--output", str(output)]
        result = subprocess.run(base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        with output.open() as stream:
            self.assertEqual(csv.DictReader(stream).fieldnames, module.FIELDS)
        a.unlink()
        self.assertEqual(subprocess.run(base, capture_output=True).returncode, 2)

    def test_report_cannot_overwrite_input(self):
        a = self.table("a", [("a", "1", "ok")])
        original = a.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), str(a), str(a), "--keys", "id", "--output", str(a)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(a.read_bytes(), original)

    def cli(self, before, after, *options, output="report.csv"):
        path = self.root / output
        result = subprocess.run([sys.executable, str(SCRIPT), str(before), str(after), "--keys", "id",
                                 "--output", str(path), *options], capture_output=True, text=True)
        rows = []
        if path.exists():
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
        return result, rows

    def test_per_column_tolerances_in_one_run(self):
        before = self.table("a", [("1", "1.0", "100.0")], ("id", "x", "y"))
        after = self.table("b", [("1", "1.0000001", "100.4")], ("id", "x", "y"))
        result, rows = self.cli(before, after, "--tol", "x=1e-3,0", "y=1,0")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual({r["metric"]: r["atol"] for r in rows if r["check_type"] == "numeric"}, {"x": "0.001", "y": "1.0"})
        self.assertEqual(self.cli(before, after, "--tol", "x=1e-3,0", "y=0.1,0", output="strict.csv")[0].returncode, 1)
        for bad in ("x=1", "x", "=1,0", "x=a,b"):
            self.assertEqual(self.cli(before, after, "--tol", bad, output="bad.csv")[0].returncode, 2)
        self.assertEqual(self.cli(before, after, "--tol", "x=-1,0", "y=1,0", output="neg.csv")[0].returncode, 2)
        self.assertEqual(self.cli(before, after, "--tol", "x=1,0", "x=2,0", output="dup.csv")[0].returncode, 2)

    def test_declared_missing_tokens_for_numeric_columns_only(self):
        before = self.table("a", [("1", "NA", "NA"), ("2", "3", "ok")])
        same = self.run_comparison(before, before, missing_values=["NA"])
        self.assertTrue(all(row["status"] == "PASS" for row in same))
        self.assertTrue(any("declared missing: ['NA']" in row["comparison_rule"] for row in same))
        self.assertTrue(any(row["status"] == "FAIL" for row in self.run_comparison(before, before)))
        changed = self.table("b", [("1", "0", "NA"), ("2", "3", "ok")])
        self.assertTrue(any(row["status"] == "FAIL" for row in self.run_comparison(before, changed, missing_values=["NA"])))
        qc = self.table("c", [("1", "NA", ""), ("2", "3", "ok")])
        self.assertTrue(any(row["check_type"] == "qc" and row["status"] == "FAIL"
                            for row in self.run_comparison(before, qc, missing_values=["NA"])))
        with self.assertRaises(ValueError):
            self.run_comparison(before, before, missing_values=["-999"])

    def test_encoding_problem_is_blocked_then_readable(self):
        path = self.root / "gbk.csv"
        path.write_bytes("id,组\n1,对照\n".encode("gbk"))
        result, rows = self.cli(path, path)
        self.assertEqual((result.returncode, rows[0]["status"]), (2, "BLOCKED"))
        self.assertEqual(self.cli(path, path, "--encoding", "gb18030", output="ok.csv")[0].returncode, 0)
        self.assertEqual(self.cli(path, path, "--encoding", "nope", output="no.csv")[0].returncode, 2)

    def test_csv_engine_error_is_blocked(self):
        path = self.root / "big.csv"
        path.write_text("id,v\n1," + "x" * (17 * 1024 * 1024))
        result, rows = self.cli(path, path)
        self.assertEqual((result.returncode, rows[0]["status"]), (2, "BLOCKED"), result.stderr[-300:])

    def test_long_text_fields_and_delimiters(self):
        path = self.table("long", [("1", "x" * 200000)], ("id", "v"))
        self.assertEqual(self.cli(path, path)[0].returncode, 0)
        (self.root / "t.tsv").write_text("id\tv\n1\t2\n")
        self.assertEqual(self.cli(self.root / "t.tsv", self.root / "t.tsv", "--delimiter", "tab", "--numeric", "v", output="t.csv")[0].returncode, 0)

    def test_only_plain_numbers_are_accepted(self):
        plain = self.table("a", [("1", "1000", "ok")])
        for text in ("1_000", "\uff11000", "1,000", "0x3e8", "1e", "."):
            with self.subTest(text):
                result = self.run_comparison(plain, self.table("b", [("1", text, "ok")]), atol=1e9)
                self.assertTrue(any(row["status"] == "FAIL" for row in result))
        for text in ("+1000", "1e3", "1000.", " 1000 ", "1.0E+03"):
            with self.subTest(text):
                result = self.run_comparison(plain, self.table("b", [("1", text, "ok")]))
                self.assertTrue(all(row["status"] == "PASS" for row in result))

    def test_default_report_is_summary_plus_failures(self):
        rows = [(str(i), "1", "ok") for i in range(50)]
        changed = rows[:-1] + [("49", "3", "ok")]
        options = ("--numeric", "value", "--qc", "qc")
        result, report = self.cli(self.table("a", rows), self.table("b", changed), *options)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(report), 4)  # two field summaries, one failure, row_count
        summary = next(r for r in report if r["metric"] == "value" and not r["sample_key"])
        self.assertEqual((summary["status"], summary["abs_diff"]), ("FAIL", "2"))
        self.assertIn("compared=50; fail=1", summary["notes"])
        self.assertEqual([r["sample_key"] for r in report if r["sample_key"]], ['{"id": "49"}'])
        self.assertEqual(len(self.cli(self.root / "a", self.root / "b", *options, "--full", output="full.csv")[1]), 101)

    def test_all_missing_columns_are_called_out(self):
        path = self.table("a", [("1", "", "ok"), ("2", "NaN", "ok")])
        report = self.cli(path, path, "--numeric", "value")[1]
        self.assertTrue(any("no finite value was compared" in r["notes"] for r in report))

    def test_unknown_metadata_is_recorded_and_announced(self):
        path = self.table("a", [("1", "1", "ok")])
        result, report = self.cli(path, path, "--method", "m")
        self.assertEqual((report[0]["dataset_id"], report[0]["method"]), ("unknown", "m"))
        self.assertIn("recorded as unknown", result.stdout)

    def test_existing_report_is_protected_and_appendable(self):
        path = self.table("a", [("1", "1", "ok")])
        (self.root / "matrix.csv").write_text("my own notes\n")
        for options in ((), ("--append",)):
            self.assertEqual(self.cli(path, path, *options, output="matrix.csv")[0].returncode, 2)
            self.assertEqual((self.root / "matrix.csv").read_text(), "my own notes\n")
        first = self.cli(path, path)[1]
        self.assertEqual(len(self.cli(path, path, "--append")[1]), 2 * len(first))
        self.assertEqual(len(self.cli(path, path, "--overwrite")[1]), len(first))


if __name__ == "__main__":
    unittest.main()
