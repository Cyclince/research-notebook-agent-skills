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
        base = [sys.executable, str(SCRIPT), str(a), str(b), "--keys", "id", "--numeric", "value", "--output", str(output)]
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


if __name__ == "__main__":
    unittest.main()
