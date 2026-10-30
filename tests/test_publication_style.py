import importlib.util
import math
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

os.environ.setdefault('MPLBACKEND', 'Agg')
import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / 'scientific-figure-workflow/assets/publication_style.py'
spec = importlib.util.spec_from_file_location('publication_style', SCRIPT)
style = importlib.util.module_from_spec(spec)
spec.loader.exec_module(style)


class PublicationStyleTests(unittest.TestCase):
    def tearDown(self):
        plt.close('all')

    def test_mm_conversion_and_invalid_dimensions(self):
        self.assertEqual(style.figure_size_mm(25.4, 50.8), (1, 2))
        for value in (0, -1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                style.figure_size_mm(value, 50)

    def test_style_is_local_even_when_plotting_raises(self):
        previous = mpl.rcParams.copy()
        with self.assertRaises(RuntimeError):
            with style.publication_style(font_size=12):
                self.assertEqual(mpl.rcParams['font.size'], 12)
                raise RuntimeError('plot failed')
        for key in ('font.size', 'font.family', 'text.usetex', 'axes.spines.top', 'savefig.bbox'):
            self.assertEqual(mpl.rcParams[key], previous[key])

    def test_exact_canvas_survives_inherited_tight_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            with mpl.rc_context({'savefig.bbox': 'tight'}):
                with style.publication_style():
                    fig, ax = plt.subplots(figsize=style.figure_size_mm(101.6, 76.2), layout='constrained')
                    ax.plot([1, 2], [1, 2], marker='o', label='Measured')
                    ax.set_xlabel('Time (s)')
                    ax.set_ylabel('Value')
                    ax.legend()
                    result = style.export_figure(fig, Path(directory) / 'figure', formats=('png', 'svg', 'pdf'), dpi=100)
            with Image.open(Path(directory) / 'figure.png') as image:
                self.assertEqual(image.size, (400, 300))
            svg = ET.parse(Path(directory) / 'figure.svg').getroot()
            self.assertEqual(svg.attrib['width'], '288pt')
            self.assertTrue(svg.findall('.//{http://www.w3.org/2000/svg}text'))
            self.assertTrue((Path(directory) / 'figure.pdf').read_bytes().startswith(b'%PDF'))
            self.assertEqual(result['visual_check'], 'NOT-RUN')
            self.assertTrue(plt.fignum_exists(fig.number))

    def test_missing_glyph_fails_before_delivery(self):
        with tempfile.TemporaryDirectory() as directory, style.publication_style():
            fig, ax = plt.subplots()
            ax.set_title(chr(0x10FFFF))
            with self.assertRaisesRegex(RuntimeError, 'Missing glyphs'):
                style.export_figure(fig, Path(directory) / 'missing')

    def test_invalid_export_options_rejected(self):
        fig, _ = plt.subplots()
        for formats in ((), ('png', 'png'), ('exe',)):
            with self.assertRaises(ValueError):
                style.export_figure(fig, 'unused', formats=formats)
        with self.assertRaises(ValueError):
            style.export_figure(fig, 'unused', dpi=0)
