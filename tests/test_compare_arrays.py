import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scientific-reproducibility-audit/scripts"
sys.path.insert(0, str(SCRIPTS))
import compare_arrays as module
from compare_csv import FIELDS

try:
    import netCDF4
except ImportError:
    netCDF4 = None


class ArrayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def npz(self, name, **arrays):
        np.savez(self.root / name, **arrays)
        return self.root / name

    def failures(self, a, b, **options):
        rows = module.compare(self.npz("a.npz", x=np.asarray(a)), self.npz("b.npz", x=np.asarray(b)), **options)
        return {row["metric"] for row in rows if row["status"] == "FAIL"}

    def test_identical_arrays_pass(self):
        for value in ([1.0, np.nan], [[1, 2], [3, 4]], ["a", "b"], [True, False], [1 + 2j], 3.0):
            self.assertEqual(self.failures(value, value), set())

    def test_tolerance_and_worst_location(self):
        a, b = np.zeros((2, 3)), np.zeros((2, 3))
        b[1, 2] = 0.1
        rows = module.compare(self.npz("a.npz", x=a), self.npz("b.npz", x=b))
        row = next(r for r in rows if r["check_type"] == "numeric")
        self.assertEqual(row["status"], "FAIL")
        self.assertIn("index (1, 2)", row["notes"])
        self.assertEqual(self.failures(a, b, tolerances={"x": (0.2, 0)}), set())

    def test_mask_infinity_shape_and_dtype_changes_fail(self):
        self.assertIn("x:missing-mask", self.failures([1.0, np.nan], [1.0, 0.0], atol=9))
        self.assertIn("x", self.failures([np.inf], [np.inf], atol=9, rtol=9))
        self.assertIn("x:shape", self.failures(np.zeros((1, 3)), np.zeros(3)))
        self.assertIn("x:dtype", self.failures(np.float32([1]), np.float64([1])))
        self.assertIn("x:nonempty", self.failures(np.zeros(0), np.zeros(0)))
        self.assertIn("x", self.failures(["a"], ["b"]))

    def test_integer_differences_are_exact(self):
        self.assertIn("x", self.failures([2**53], [2**53 + 1]))
        self.assertIn("x", self.failures([-2**63], [2**63 - 1], atol=1e18))
        self.assertIn("x", self.failures(np.uint8([0]), np.uint8([255]), atol=1))
        self.assertIn("x", self.failures(np.uint8([255]), np.uint8([0]), atol=1))

    def test_variable_set_changes_fail(self):
        rows = module.compare(self.npz("a.npz", x=[1], y=[1]), self.npz("b.npz", x=[1]))
        self.assertTrue(any(r["metric"] == "y" and r["status"] == "FAIL" for r in rows))
        with self.assertRaises(ValueError):
            module.compare(self.root / "a.npz", self.root / "a.npz", tolerances={"typo": (1, 1)})

    def test_cli_codes_schema_and_refused_inputs(self):
        a = self.npz("a.npz", x=[1.0])
        b = self.npz("b.npz", x=[2.0])
        np.savez(self.root / "object.npz", x=np.array([{}], dtype=object))
        (self.root / "bad.npz").write_text("not an archive")
        (self.root / "x.mat").write_text("")
        for other, expected in ((a, 0), (b, 1), (self.root / "object.npz", 2), (self.root / "bad.npz", 2),
                                (self.root / "x.mat", 2), (self.root / "absent.npz", 2)):
            output = self.root / f"{other.name}.csv"
            # Run from elsewhere: the script must find its sibling module by itself.
            result = subprocess.run([sys.executable, str(SCRIPTS / "compare_arrays.py"), str(a), str(other),
                                     "--output", str(output)], capture_output=True, text=True, cwd=self.root)
            self.assertEqual(result.returncode, expected, (other, result.stdout, result.stderr))
            with output.open(newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(reader.fieldnames, FIELDS)
                self.assertEqual(expected == 2, any(r["status"] == "BLOCKED" for r in reader))

    @unittest.skipUnless(netCDF4, "netCDF4 not installed")
    def test_netcdf_mask_units_and_dimensions(self):
        def write(name, values, units="mm", dimension="time"):
            path = self.root / name
            with netCDF4.Dataset(path, "w") as dataset:
                dataset.createDimension(dimension, 3)
                variable = dataset.createGroup("g").createVariable("v", "f8", (dimension,), fill_value=-999.0)
                variable.units = units
                variable[:] = values
                dataset.createVariable("scalar", "i4")[...] = 5
                dataset.createVariable("label", str, (dimension,))[:] = np.array(["a", "b", "c"], dtype=object)
            return path

        def failed(path):
            return {r["metric"] for r in module.compare(base, path) if r["status"] == "FAIL"}

        base = write("base.nc", np.ma.array([1, 2, 3], mask=[0, 1, 0]))
        self.assertEqual(failed(write("same.nc", np.ma.array([1, 7, 3], mask=[0, 1, 0]))), set())
        self.assertEqual(failed(write("mask.nc", [1, 0, 3])), {"g/v:missing-mask"})
        self.assertEqual(failed(write("units.nc", np.ma.array([1, 2, 3], mask=[0, 1, 0]), units="cm")), {"g/v:attributes"})
        self.assertIn("g/v:dimensions", failed(write("dims.nc", np.ma.array([1, 2, 3], mask=[0, 1, 0]), dimension="lat")))


if __name__ == "__main__":
    unittest.main()
