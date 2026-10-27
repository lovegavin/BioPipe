"""Artifact SOP for the two plot operators not exercised by route tests."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task import Context, run


def _context(tmp_path):
    return Context(tmp_path, {})


def test_line_plot_writes_nonempty_png(tmp_path):
    data = np.array(
        [[0.0, 0.50, 0.10, 0.10], [1000.0, 0.52, 0.12, 0.22], [2000.0, 0.49, 0.09, 0.31]],
        dtype=np.float32,
    )
    form = Form(
        data=data,
        dims=["window", "statistic"],
        labels={"window": {"w0": 0, "w1": 1, "w2": 2},
                "statistic": {"start": 0, "gc": 1, "gc_skew": 2, "cumulative_gc": 3}},
        info={"missing_code": np.nan},
    )
    ctx = _context(tmp_path)
    ctx["profile"] = form
    run(ctx, [{"name": "line", "inputs": ["profile"],
              "params": {"dim": "statistic", "x_label": "start", "y_label": "gc",
                         "filename": "line.png", "title": "GC"}}])
    path = tmp_path / "output" / "figures" / "line.png"
    assert path.exists() and path.stat().st_size > 0


def test_enrichment_plot_writes_nonempty_png(tmp_path):
    data = np.array(
        [[0.001, 8.0], [0.004, 5.0], [0.010, 3.0], [0.020, 2.0]],
        dtype=np.float32,
    )
    form = Form(
        data=data,
        dims=["term", "statistic"],
        labels={"term": {"GO:0001": 0, "GO:0002": 1, "GO:0003": 2, "GO:0004": 3},
                "statistic": {"Q_VALUE": 0, "n_hit": 1}},
        info={"missing_code": np.nan},
    )
    ctx = _context(tmp_path)
    ctx["enriched"] = form
    run(ctx, [{"name": "enrichment_plot", "inputs": ["enriched"],
              "params": {"q_column": "Q_VALUE", "size_column": "n_hit",
                         "top_n": 3, "filename": "enrichment.png"}}])
    path = tmp_path / "output" / "figures" / "enrichment.png"
    assert path.exists() and path.stat().st_size > 0
