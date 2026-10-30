"""Cronbach's alpha reliability coefficient."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._multivariate35_common import frame_matrix


class CronbachAlphaStep(Step):
    """Cronbach's alpha for a set of continuous items."""

    name = "cronbach_alpha"
    title = "Cronbach's alpha"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "item")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "item"},
            "items": {"type": "array", "items": {"type": "string"}},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "item")
        out_name = ctx.step_params.get("output", self.name)
        items = list(ctx.step_params.get("items") or [])
        samples, names, matrix = frame_matrix(
            form, sample_dim, feature_dim, "cronbach_alpha", items or None
        )
        keep = np.isfinite(matrix).all(axis=1)
        matrix = matrix[keep]
        samples = [name for name, ok in zip(samples, keep) if ok]
        n, k = matrix.shape
        if k < 2:
            raise StepError("cronbach_alpha: at least two items are required")
        if n < 3:
            raise StepError("cronbach_alpha: fewer than three complete subjects")

        item_variance = np.var(matrix, axis=0, ddof=1)
        total = matrix.sum(axis=1)
        total_variance = float(np.var(total, ddof=1))
        if total_variance <= 0:
            raise StepError("cronbach_alpha: total scores have zero variance")
        if np.any(item_variance <= 0):
            raise StepError("cronbach_alpha: every item must have positive variance")

        raw_alpha = float(
            (k / (k - 1)) * (1.0 - float(item_variance.sum()) / total_variance)
        )
        correlation = np.corrcoef(matrix, rowvar=False)
        if not np.isfinite(correlation).all():
            raise StepError("cronbach_alpha: item correlations are not finite")
        off_diagonal = (correlation.sum() - k) / (k * (k - 1))
        denominator = 1.0 + (k - 1) * float(off_diagonal)
        if denominator <= 0:
            raise StepError("cronbach_alpha: standardized alpha is undefined")
        std_alpha = float(k * off_diagonal / denominator)

        out = make_form(
            [
                [raw_alpha],
                [std_alpha],
                [float(off_diagonal)],
                [float(k)],
                [float(n)],
            ],
            ["statistic", "value"],
            {
                "statistic": {
                    "raw_alpha": 0,
                    "std_alpha": 1,
                    "average_r": 2,
                    "n_items": 3,
                    "n_subjects": 4,
                },
                "value": {"value": 0},
            },
        )
        out.info.update(
            {
                "missing_code": np.nan,
                "method": "cronbach_alpha",
                "items": names,
                "n_subjects": int(n),
                "n_items": int(k),
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "raw_alpha": raw_alpha,
            "std_alpha": std_alpha,
            "average_r": float(off_diagonal),
            "n_items": int(k),
            "n_subjects": int(n),
            "items": names,
        }
        print(
            f"[cronbach_alpha] raw={raw_alpha:.6f}, "
            f"std={std_alpha:.6f}, k={k}, n={n}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
