import importlib.util
import math
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('MPLBACKEND', 'Agg')
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / 'scientific-figure-workflow/assets/publication_style.py'
spec = importlib.util.spec_from_file_location('publication_style', SCRIPT)
style = importlib.util.module_from_spec(spec)
spec.loader.exec_module(style)


class PublicationStyleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.addCleanup(plt.close, 'all')

    def figure(self, **kwargs):
        fig, ax = plt.subplots(layout='constrained', **kwargs)
        ax.plot([1, 2], [1, 2], marker='o')
        return fig, ax

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
        with mpl.rc_context({'savefig.bbox': 'tight'}):
            with style.publication_style():
                fig, ax = plt.subplots(figsize=style.figure_size_mm(101.6, 76.2), layout='constrained')
                ax.plot([1, 2], [1, 2], marker='o', label='Measured')
                ax.set_xlabel('Time (s)')
                ax.set_ylabel('Value')
                ax.legend()
                result = style.export_figure(fig, self.root / 'figure', dpi=100)
        with Image.open(self.root / 'figure.png') as image:
            self.assertEqual(image.size, (400, 300))
        self.assertEqual([p.name for p in self.root.iterdir()], ['figure.png'])
        for extension in ('tif', 'tiff'):
            style.export_figure(fig, self.root / 'figure', format=extension, dpi=100)
            with Image.open(self.root / f'figure.{extension}') as image:
                self.assertEqual((image.format, image.size), ('TIFF', (400, 300)))
        self.assertEqual(result['visual_check'], 'NOT-RUN')
        self.assertTrue(plt.fignum_exists(fig.number))

    def test_tiff_is_rgb_lzw_at_requested_dpi(self):
        fig, _ = self.figure(figsize=(4, 3))
        style.export_figure(fig, self.root / 'a', format='tiff', dpi=600)
        with Image.open(self.root / 'a.tiff') as image:
            self.assertEqual((image.mode, image.info['compression']), ('RGB', 'tiff_lzw'))
            self.assertEqual(tuple(map(float, image.info['dpi'])), (600, 600))
        self.assertLess((self.root / 'a.tiff').stat().st_size, 2400 * 1800)

    def test_transparent_tiff_keeps_alpha(self):
        fig, ax = self.figure()
        ax.patch.set_alpha(0)
        style.export_figure(fig, self.root / 'a', format='tif', facecolor='none')
        with Image.open(self.root / 'a.tif') as image:
            self.assertEqual(image.mode, 'RGBA')

    def test_vector_only_on_explicit_request_and_single_file(self):
        for extension, magic in (('pdf', b'%PDF'), ('svg', b'<?xml')):
            directory = self.root / extension
            fig, _ = self.figure()
            style.export_figure(fig, directory / 'a', format=extension)
            self.assertEqual([p.name for p in directory.iterdir()], [f'a.{extension}'])
            self.assertTrue((directory / f'a.{extension}').read_bytes().startswith(magic))

    def test_missing_glyph_fails_and_preserves_previous_file(self):
        with style.publication_style():
            fig, ax = self.figure()
            style.export_figure(fig, self.root / 'a')
            before = (self.root / 'a.png').read_bytes()
            ax.set_title(chr(0x10FFFF))
            with self.assertRaisesRegex(RuntimeError, 'Missing glyphs'):
                style.export_figure(fig, self.root / 'a')
        self.assertEqual((self.root / 'a.png').read_bytes(), before)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_content_outside_canvas_fails(self):
        fig, ax = plt.subplots(figsize=style.figure_size_mm(40, 30))
        ax.plot([1, 2])
        ax.set_ylabel('very long label ' * 8)
        with self.assertRaisesRegex(RuntimeError, 'exceeds the canvas'):
            style.export_figure(fig, self.root / 'a')
        self.assertEqual(list(self.root.iterdir()), [])
        result = style.export_figure(fig, self.root / 'a', allow_overflow=True)
        self.assertEqual(result['checks']['within-canvas'], 'PASS-WITH-DIFF')
        self.assertEqual(style.export_figure(fig, self.root / 'b', exact_size=False)['checks']['within-canvas'], 'NOT-RUN')

    def test_out_of_range_ticks_and_clipped_data_do_not_count_as_overflow(self):
        fig, ax = self.figure()
        ax.plot([0, 100], [0, 100])
        ax.set_xlim(1, 2)
        self.assertEqual(style.canvas_overflow_mm(fig), {})

    def test_empty_figures_and_panels_fail(self):
        nan = float('nan')
        fillers = {
            'nothing': lambda ax: None, 'nan line': lambda ax: ax.plot([1, 2], [nan, nan]),
            'empty scatter': lambda ax: ax.scatter([], []), 'nan scatter': lambda ax: ax.scatter([1], [nan]),
            'nan bar': lambda ax: ax.bar([1], [nan]), 'nan image': lambda ax: ax.imshow([[nan, nan]]),
            'nan mesh': lambda ax: ax.pcolormesh(np.full((2, 2), nan)), 'reference only': lambda ax: ax.axhline(0),
            'span only': lambda ax: ax.axvspan(0, 1), 'text only': lambda ax: ax.text(0, 0, 'x')}
        for name, fill in fillers.items():
            with self.subTest(name), mpl.rc_context({'axes.grid': True}):
                fig, axes = plt.subplots(1, 2)
                axes[0].plot([1, 2])
                fill(axes[1])
                self.assertEqual(style.empty_axes(fig), [1])
                with self.assertRaisesRegex(RuntimeError, 'Empty'):
                    style.export_figure(fig, self.root / 'a')
                plt.close(fig)
        with self.assertRaisesRegex(RuntimeError, 'Empty'):
            style.export_figure(plt.figure(), self.root / 'a')

    def test_common_plots_colorbars_and_legend_panels_are_not_empty(self):
        grid = np.arange(9.0).reshape(3, 3)
        fillers = {
            'bar': lambda ax: ax.bar([1], [0]), 'hist': lambda ax: ax.hist([1, 2]), 'box': lambda ax: ax.boxplot([1, 2, 3]),
            'violin': lambda ax: ax.violinplot([1, 2, 3]), 'band': lambda ax: ax.fill_between([1, 2], [0, 0], [1, 1]),
            'error': lambda ax: ax.errorbar([1], [1], yerr=[1], fmt='none'), 'hexbin': lambda ax: ax.hexbin([1, 2], [1, 2], gridsize=3),
            'contour': lambda ax: ax.contourf(grid), 'mesh': lambda ax: ax.pcolormesh(grid), 'pie': lambda ax: ax.pie([1, 2]),
            'rgb': lambda ax: ax.imshow(np.zeros((2, 2, 3))), 'offset': lambda ax: ax.scatter([0.1], [1])}
        for name, fill in fillers.items():
            with self.subTest(name):
                fig, ax = plt.subplots()
                fill(ax)
                self.assertEqual(style.empty_axes(fig), [])
                plt.close(fig)
        fig, axes = plt.subplots(1, 2)
        fig.colorbar(axes[0].imshow(grid))
        axes[1].set_axis_off()
        self.assertEqual(style.empty_axes(fig), [])

    def test_invalid_export_options_rejected(self):
        fig, _ = self.figure()
        for format in ('jpg', 'eps', 'exe', ('png', 'tif')):
            with self.assertRaises(ValueError):
                style.export_figure(fig, 'unused', format=format)
        with self.assertRaises(ValueError):
            style.export_figure(fig, 'unused', dpi=0)


if __name__ == '__main__':
    unittest.main()
