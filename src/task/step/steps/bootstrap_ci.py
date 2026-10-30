"""Bootstrap confidence intervals for per-feature means or medians."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class BootstrapCiStep(Step):
    name = "bootstrap_ci"
    title = "Bootstrap confidence interval"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "statistic": {"type": "string", "enum": ["mean", "median"], "default": "mean"},
            "n_boot": {"type": "integer", "minimum": 100, "maximum": 100000, "default": 2000},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "random_state": {"type": "integer", "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x, samples, features = matrix(inputs[0], sample_dim, feature_dim)
        n_boot = int(ctx.step_params.get("n_boot", 2000))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        if not 0.0 < confidence < 1.0:
            raise StepError(f"bootstrap_ci: confidence must be in (0, 1), got {confidence}")
        stat = ctx.step_params.get("statistic", "mean")
        rng = np.random.default_rng(int(ctx.step_params.get("random_state", 0)))
        out = np.full((x.shape[1], 3), np.nan, dtype=np.float64)
        for j in range(x.shape[1]):
            values = x[:, j]
            if np.isnan(values).all():
                continue
            estimate = np.nanmean(values) if stat == "mean" else np.nanmedian(values)
            valid = values[np.isfinite(values)]
            if len(valid) == 0:
                continue
            draws = rng.choice(valid, size=(n_boot, len(valid)), replace=True)
            boot = draws.mean(axis=1) if stat == "mean" else np.median(draws, axis=1)
            alpha = (1.0 - confidence) / 2.0
            lower, upper = np.percentile(boot, [100 * alpha, 100 * (1 - alpha)])
            out[j] = (estimate, lower, upper)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32), dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"estimate": 0, "lower": 1, "upper": 2},
            },
            info={"method": f"bootstrap_{stat}", "n_boot": n_boot, "confidence": confidence},
        )
        self._export = {"n_samples": len(samples), "n_features": int(x.shape[1]), "n_boot": n_boot}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
