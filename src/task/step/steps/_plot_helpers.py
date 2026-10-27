"""Publication figures, independent of Studio's interactive preview/theme."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cycler import cycler


def setup_style(ctx=None) -> None:
    """Apply for every plot: another operator may have changed global rcParams."""
    params = ctx.step_params if ctx is not None else {}
    size = float(params.get("figure_font_size", 8))
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Arial"],
        "font.size": size, "axes.labelsize": size, "axes.titlesize": size + 1,
        "xtick.labelsize": size, "ytick.labelsize": size, "legend.fontsize": size,
        "text.color": "#222222", "axes.labelcolor": "#222222",
        "axes.edgecolor": "#333333", "xtick.color": "#333333", "ytick.color": "#333333",
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "savefig.edgecolor": "white",
        "savefig.transparent": False, "axes.grid": False, "grid.color": "#dddddd",
        "axes.prop_cycle": cycler(color=["#0072B2", "#D55E00", "#009E73", "#CC79A7",
                                          "#E69F00", "#56B4E9", "#000000"]),
        "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "lines.linewidth": 1.0, "legend.frameon": False,
        "figure.dpi": 100, "savefig.dpi": 300, "savefig.bbox": None,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    })


def save_figure(fig, ctx, filename: str) -> str:
    """Persist PNG/PDF/SVG at run time, retaining the requested original format.

    Text/axes stay vector in PDF/SVG. Dense artists explicitly rasterized by the
    operator use the same DPI as PNG. Physical dimensions are not cropped away.
    """
    try:
        params = ctx.step_params
        base = Path(ctx.memory.run_dir if ctx.memory else ctx.out_dir)
        directory = (base / "figures").resolve()
        path = (directory / filename).resolve()
        if not path.is_relative_to(directory) or path.suffix.lower() not in {
            ".png", ".pdf", ".svg", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"
        }:
            raise ValueError("Figure filename must be an image/PDF inside the figures directory")
        path = path.with_suffix(path.suffix.lower())
        path.parent.mkdir(parents=True, exist_ok=True)
        formats = list(dict.fromkeys([path.suffix[1:].lower(), "png", "pdf", "svg"]))
        original = path
        counter = 1
        while any(path.with_suffix('.' + fmt).exists() for fmt in [*formats, "figure.json"]):
            counter += 1
            path = original.with_name(f"{original.stem}-{counter}{original.suffix}")
        width, height = fig.get_size_inches() * 25.4
        requested_width = params.get("figure_width_mm")
        requested_height = params.get("figure_height_mm")
        if requested_width is not None:
            height *= float(requested_width) / width
            width = float(requested_width)
        elif width > 180:
            height *= 180 / width
            width = 180.0
        if requested_height is not None:
            height = float(requested_height)
        dpi = int(params.get("figure_dpi", 300))
        if not (width > 0 and height > 0 and dpi > 0):
            raise ValueError("Figure dimensions and DPI must be positive")
        fig.set_size_inches(width / 25.4, height / 25.4, forward=True)
        fig.set_facecolor("white")
        fig.tight_layout(pad=0.8)
        outputs = []
        with matplotlib.rc_context({"pdf.fonttype": 42, "svg.fonttype": "none", "savefig.bbox": None}):
            for fmt in formats:
                target = path.with_suffix('.' + fmt)
                fig.savefig(target, format=fmt, dpi=dpi, bbox_inches=None,
                            facecolor="white", edgecolor="white", transparent=False)
                outputs.append({"format": fmt, "path": str(target), "filename": target.name,
                                "width_mm": float(width), "height_mm": float(height), "dpi": dpi})
        path.with_suffix('.figure.json').write_text(json.dumps(outputs, indent=2), encoding="utf-8")
        return str(path)
    finally:
        plt.close(fig)


def figure_report(report: dict) -> dict:
    """Expose saved files in step reports, including isolated operator workers."""
    path = Path(report.get("path") or report["figure_path"])
    outputs = json.loads(path.with_suffix('.figure.json').read_text(encoding="utf-8"))
    return {**report, "path": str(path), "filename": path.name, "figures": outputs}
