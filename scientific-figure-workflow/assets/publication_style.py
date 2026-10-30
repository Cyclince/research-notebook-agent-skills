"""Optional layout/export helpers; data selection and plotting stay in the notebook."""
from contextlib import contextmanager
import math
from pathlib import Path
import warnings

import matplotlib as mpl
from matplotlib import font_manager


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
        'svg.fonttype': 'none', 'pdf.fonttype': 42, 'savefig.bbox': None,
    }):
        yield


def export_figure(fig, output_stem, *, formats=('pdf', 'png'), dpi=300,
                  exact_size=True, facecolor='white'):
    """Save supplied figure; return evidence, not a scientific/visual PASS.

    Use inside publication_style, after checking data and adding plot artists.
    Files produced before a render/save failure must not be treated as accepted.
    """
    formats = tuple(formats)
    if not formats or len(formats) != len(set(formats)) or any(x not in ('pdf', 'svg', 'png') for x in formats):
        raise ValueError('Specify unique output formats from pdf, svg, png')
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError('DPI must be finite and positive')
    output_stem = Path(output_stem)
    paths = [Path(str(output_stem) + '.' + ext) for ext in formats]
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        fig.canvas.draw()
        glyphs = [str(w.message) for w in caught if 'glyph' in str(w.message).lower() and 'missing' in str(w.message).lower()]
        if glyphs:
            raise RuntimeError('Missing glyphs: configure a font covering actual labels')
        # Reset inherited tight cropping too; exact canvas dimensions are preserved.
        with mpl.rc_context({'savefig.bbox': None}):
            for path in paths:
                fig.savefig(path, dpi=dpi, facecolor=facecolor,
                            bbox_inches=None if exact_size else 'tight')
        glyphs = [str(w.message) for w in caught if 'glyph' in str(w.message).lower() and 'missing' in str(w.message).lower()]
    if glyphs:
        raise RuntimeError('Missing glyphs during save: exported files are not accepted')
    for warning in caught:
        warnings.warn(str(warning.message), warning.category, stacklevel=2)
    return {'files': [str(p) for p in paths], 'dpi': dpi,
            'requested_size_mm': [float(x) * 25.4 for x in fig.get_size_inches()],
            'exact_size': exact_size, 'visual_check': 'NOT-RUN',
            'note': 'Cropped outputs require actual-size inspection' if not exact_size else 'Inspect canvas, labels and clipping at final scale'}
