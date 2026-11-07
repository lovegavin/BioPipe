"""Scale-free topology fit over a range of soft-thresholding powers.

Mirrors WGCNA's ``pickSoftThreshold`` scale-free fit: for every candidate
power the connectivity ``k = sum(|cor|^power) - 1`` is discretised into equal
width bins, the log10 histogram is fitted with a linear model, and the R^2,
slope and truncated-exponential adjusted R^2 are reported.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._coexpression_common import (
    correlation,
    expression_matrix,
    scale_free_fit,
    select_features,
)

_STATISTICS = {
    "r_squared": 0,
    "slope": 1,
    "adj_r_squared": 2,
    "mean_k": 3,
    "median_k": 4,
    "max_k": 5,
}


def parse_powers(text: str) -> list[int]:
    if isinstance(text, (list, tuple)):
        values = [int(v) for v in text]
    else:
        values = [int(part) for part in str(text).replace(";", ",").split(",") if part.strip()]
    powers = sorted({v for v in values if v > 0})
    if not powers:
        raise StepError("at least one positive power is required")
    return powers


def soft_threshold_table(R: np.ndarray, powers: list[int], n_bins: int = 10):
    rows = []
    absolute = np.abs(R)
    for power in powers:
        k = np.power(absolute, float(power)).sum(axis=1) - 1.0
        fit = scale_free_fit(k, n_bins=n_bins)
        rows.append(
            {
                "power": power,
                "r_squared": fit["r_squared"],
                "slope": fit["slope"],
                "adj_r_squared": fit["adj_r_squared"],
                "mean_k": float(np.mean(k)),
                "median_k": float(np.median(k)),
                "max_k": float(np.max(k)),
            }
        )
    return rows


def suggest_power(rows: list[dict], r2_cut: float, slope_cut: float) -> int:
    for row in rows:
        if (
            np.isfinite(row["r_squared"])
            and row["r_squared"] >= r2_cut
            and np.isfinite(row["slope"])
            and row["slope"] >= slope_cut
        ):
            return int(row["power"])
    return int(rows[-1]["power"])


class WgcnaSoftThresholdStep(Step):
    """Fit scale-free topology statistics for candidate adjacency powers."""

    provider = "operon-core"
    parameters_file = "wgcna_soft_threshold.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "wgcna_soft_threshold",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Scale-free topology fit for soft-threshold powers",
        "description": (
            "Computes the signed correlation network for a range of powers, "
            "derives the connectivity distribution and reports the scale-free "
            "fit R^2, slope and truncated-exponential adjusted R^2, together "
            "with a suggested power."
        ),
        "category": "Omics",
        "icon": "TrendingUp",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "sample",
                        "feature",
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        shape = inputs[0].data.shape if inputs else (0, 0)
        features = min(int(params.get("max_features", 0)) or shape[-1], shape[-1])
        return (max(int(features) ** 2 * 8, 8 << 20), 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample"))
        feature_dim = str(params.get("feature_dim", "feature"))
        X, samples, features = expression_matrix(inputs[0], sample_dim, feature_dim)
        keep = select_features(X, int(params.get("max_features", 0) or 0))
        R = correlation(X[:, keep])
        powers = parse_powers(params.get("powers", "1,2,3,4,5,6,7,8,9,10,12,14,16,18,20"))
        rows = soft_threshold_table(R, powers, n_bins=int(params.get("n_bins", 10)))
        suggested = suggest_power(
            rows,
            float(params.get("r2_cut", 0.8)),
            float(params.get("slope_cut", -1.5)),
        )
        data = np.array(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float64
        )
        out_name = str(params.get("output", "thresholds"))
        out = Form(
            data=data,
            dims=["power", "statistic"],
            labels={
                "power": {str(row["power"]): index for index, row in enumerate(rows)},
                "statistic": dict(_STATISTICS),
            },
            info={
                "n_samples": len(samples),
                "n_features": int(keep.size),
                "suggested_power": suggested,
                "powers": [int(row["power"]) for row in rows],
            },
        )
        out.validate()
        ctx[out_name] = out

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "thresholds"))]
        powers = [int(p) for p in form.labels["power"]]
        r2 = [float(v) for v in form.data[:, _STATISTICS["r_squared"]]]
        suggested = int(form.info.get("suggested_power", powers[-1]))
        index = powers.index(suggested)
        return {
            "n_powers": len(powers),
            "n_samples": int(form.info["n_samples"]),
            "n_features": int(form.info["n_features"]),
            "suggested_power": suggested,
            "r_squared_at_suggested": r2[index],
            "slope_at_suggested": float(form.data[index, _STATISTICS["slope"]]),
            "max_r_squared": float(np.nanmax(r2)),
        }
