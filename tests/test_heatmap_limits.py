"""Heatmap must refuse huge matrices before Matplotlib resamples them."""
from __future__ import annotations

import numpy as np
import pytest

from biopipe_sdk.testing import run_operator
from src.core import Form, StepError
from src.task.step.steps.heatmap import HeatmapStep


def _form(rows, cols):
    data = np.zeros((rows, cols), dtype=np.float32)
    data[0, 0] = 1.0
    return Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {f"f{i}": i for i in range(rows)},
            "sample": {f"s{i}": i for i in range(cols)},
        },
        info={"missing_code": np.nan},
    )


def test_heatmap_rejects_matrix_above_max_cells():
    with pytest.raises(StepError, match="max_cells"):
        run_operator(HeatmapStep, [_form(3000, 3000)], {
            "dim": "feature",
            "other_dim": "sample",
            "select": "all",
            "filename": "too_large.png",
        })


def test_heatmap_clamps_auto_figsize_pixels():
    # 30 x 3000 is below max_cells but would auto-size to ~541 inches wide.
    report = run_operator(HeatmapStep, [_form(30, 3000)], {
        "dim": "feature",
        "other_dim": "sample",
        "select": "variance",
        "top_n": 30,
        "cluster_rows": False,
        "cluster_cols": False,
        "filename": "clamped.png",
    })
    assert report["n_rows"] == 30
    assert report["n_cols"] == 3000
    assert report["figsize"][0] < 541
