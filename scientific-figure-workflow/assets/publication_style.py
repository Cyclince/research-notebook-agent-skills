"""Optional layout/export helpers; data selection and plotting stay in the notebook."""
from contextlib import contextmanager
import io
import math
import os
from pathlib import Path
import warnings

import matplotlib as mpl
from matplotlib import collections, font_manager
import numpy as np
from PIL import Image

RASTER, VECTOR = ('png', 'tif', 'tiff'), ('pdf', 'svg')
CANVAS_TOLERANCE_MM = 0.1


def figure_size_mm(width_mm, height_mm):
    """Return inches without changing the intended physical canvas."""
    if not all(math.isfinite(x) and x > 0 for x in (width_mm, height_mm)):
        raise ValueError('Figure dimensions must be finite and positive')
    return width_mm / 25.4, height_mm / 25.4


@contextmanager
def publication_style(*, font_family='DejaVu Sans', font_size=9, line_width=1.0,
                      hide_top_right=True):
    """Local, configurable style; no global TeX or font dependencies are introduced."""
    if not all(math.isfinite(x) and x > 0 for x in (font_size, line_width)):
        raise ValueError('Font size and line width must be finite and positive')
    # Availability is not glyph coverage: export_figure checks the actual render too.
    font_manager.findfont(font_manager.FontProperties(family=font_family), fallback_to_default=False)
    with mpl.rc_context({
        'font.family': font_family, 'font.size': font_size,
        'axes.linewidth': line_width, 'lines.linewidth': line_width,
        'axes.spines.top': not hide_top_right, 'axes.spines.right': not hide_top_right,
        'legend.frameon': False, 'text.usetex': False,
        'savefig.bbox': None,
    }):
        yield


def _has_finite(vertices):
    vertices = np.ma.filled(np.ma.asarray(vertices, dtype=float), np.nan)
    return vertices.size > 0 and bool(np.isfinite(vertices).all(axis=-1).any())


def _in_data(artist, ax):
    """Reference lines/spans (axhline, axvspan) are not data in both directions."""
    return all(artist.get_transform().contains_branch_seperately(ax.transData))


def axes_has_data(ax):
    """True if a visible artist holds at least one finite data position.

    It cannot judge whether the values are correct, or lie inside the axis limits.
    """
    for line in ax.lines:
        if line.get_visible() and _in_data(line, ax) and _has_finite(line.get_xydata()):
            return True
    for image in ax.images:
        values = np.ma.masked_invalid(np.ma.asarray(image.get_array(), dtype=float))
        if image.get_visible() and values.count():
            return True
    for patch in ax.patches:
        if patch.get_visible() and _in_data(patch, ax):
            if _has_finite(patch.get_patch_transform().transform(patch.get_path().vertices)):
                return True
    for item in ax.collections:
        if not item.get_visible():
            continue
        if isinstance(item, collections.PathCollection):
            if _has_finite(item.get_offsets()):
                return True
        elif isinstance(item, collections.QuadMesh):
            if np.ma.masked_invalid(np.ma.asarray(item.get_array(), dtype=float)).count():
                return True
        elif any(_has_finite(path.vertices) for path in item.get_paths()):
            return True
    return False


def empty_axes(fig):
    """Indices of visible framed axes without data; axis('off') panels are exempt."""
    return [index for index, ax in enumerate(fig.axes)
            if ax.get_visible() and ax.axison and not axes_has_data(ax)]


def canvas_overflow_mm(fig):
    """How far drawn content (labels, legends, titles) extends beyond each canvas side."""
    box, (width, height) = fig.get_tightbbox(), fig.get_size_inches()
    sides = {'left': -box.x0, 'bottom': -box.y0, 'right': box.x1 - width, 'top': box.y1 - height}
    return {name: round(float(value) * 25.4, 2) for name, value in sides.items()
            if value * 25.4 > CANVAS_TOLERANCE_MM}


def _missing_glyphs(caught):
    return [str(w.message) for w in caught
            if 'glyph' in str(w.message).lower() and 'missing' in str(w.message).lower()]


def export_figure(fig, output_stem, *, format='png', dpi=300, exact_size=True,
                  facecolor='white', allow_empty_axes=False, allow_overflow=False):
    """Save supplied figure in one format; return evidence, not a scientific/visual PASS.

    Use inside publication_style, after checking data and adding plot artists. Default is
    PNG. TIFF is written as RGB with LZW. Use pdf/svg only when the target specification
    asks for vector art. Nothing is written unless all render checks pass.
    """
    if format not in RASTER + VECTOR:
        raise ValueError('Specify one output format: png, tif, tiff, pdf or svg')
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError('DPI must be finite and positive')
    path = Path(str(output_stem) + '.' + format)
    empty = empty_axes(fig)
    if not fig.axes or (empty and not allow_empty_axes):
        raise RuntimeError(f'Empty figure or axes {empty}: check filtering and upstream results')
    tiff = format in ('tif', 'tiff')
    buffer = io.BytesIO()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.canvas.draw()
        if _missing_glyphs(caught):
            raise RuntimeError('Missing glyphs: configure a font covering actual labels')
        overflow = canvas_overflow_mm(fig) if exact_size else {}
        if overflow and not allow_overflow:
            raise RuntimeError(f'Content exceeds the canvas (mm): {overflow}; enlarge it or shorten labels')
        # Reset inherited tight cropping too; exact canvas dimensions are preserved.
        with mpl.rc_context({'savefig.bbox': None, 'pdf.fonttype': 42}):
            fig.savefig(buffer, format='png' if tiff else format, dpi=dpi, facecolor=facecolor,
                        bbox_inches=None if exact_size else 'tight')
    if _missing_glyphs(caught):
        raise RuntimeError('Missing glyphs during save: nothing was exported')
    if tiff:
        with Image.open(buffer) as image:
            rendered = image.convert('RGBA')
        # Keep alpha only when it is really used.
        if rendered.getchannel('A').getextrema()[0] == 255:
            rendered = rendered.convert('RGB')
        output = io.BytesIO()
        rendered.save(output, format='TIFF', compression='tiff_lzw', dpi=(dpi, dpi))
        buffer = output
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(buffer.getvalue())
    os.replace(temporary, path)
    for warning in caught:
        warnings.warn(str(warning.message), warning.category, stacklevel=2)
    return {'files': [str(path)], 'dpi': dpi,
            'requested_size_mm': [float(x) * 25.4 for x in fig.get_size_inches()],
            'exact_size': exact_size, 'empty_axes': empty, 'overflow_mm': overflow,
            'checks': {'nonempty': 'PASS' if not empty else 'PASS-WITH-DIFF', 'no-glyph-warning': 'PASS',
                       'within-canvas': ('PASS-WITH-DIFF' if overflow else 'PASS') if exact_size else 'NOT-RUN'},
            'visual_check': 'NOT-RUN',
            'note': 'Cropped outputs require actual-size inspection' if not exact_size else 'Inspect overlap, labels and legibility at final scale'}
