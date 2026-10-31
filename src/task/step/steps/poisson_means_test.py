"""Exact two-sample Poisson rate test via conditional binomial."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form
from ._tests39_common import select_groups

_COLUMNS = [
    "count_a", "count_b", "n_a", "n_b", "rate_a", "rate_b",
    "rate_ratio", "p", "ci_low", "ci_high",
]


class PoissonMeansTestStep(Step):
    name = "poisson_means_test"
    title = "Exact two-sample Poisson rate test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = []
    dependency_imports = []
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "group_a": {"type": "string"},
            "group_b": {"type": "string"},
            "alternative": {"type": "string", "enum": ["two-sided", "less", "greater"], "default": "two-sided"},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        data, codes, _samples, group_a, group_b = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"], ctx.step_params["group_a"], ctx.step_params["group_b"],
            "poisson_means_test",
        )
        counts = np.asarray(data, dtype=np.float64)
        if not np.isfinite(counts).all() or np.any(counts < 0):
            raise StepError("poisson_means_test: counts must be finite and non-negative")
        if np.any(np.abs(counts - np.rint(counts)) > 1e-8):
            raise StepError("poisson_means_test: counts must be integer-valued")
        features = labels_in_order(expr, feature_dim)
        rows = []
        for j in range(counts.shape[1]):
            a = counts[codes == 0, j]
            b = counts[codes == 1, j]
            k1 = float(a.sum())
            k2 = float(b.sum())
            n1 = float(a.size)
            n2 = float(b.size)
            total = k1 + k2
            rate_a = k1 / n1
            rate_b = k2 / n2
            if total == 0:
                rows.append([k1, k2, n1, n2, rate_a, rate_b, np.nan, 1.0, np.nan, np.nan])
                continue
            result = stats.binomtest(
                int(k1), int(total), n1 / (n1 + n2), alternative=alternative
            )
            ci = result.proportion_ci(confidence_level=confidence, method="exact")
            p = float(result.pvalue)
            if k2 == 0:
                ratio = 0.0 if k1 == 0 else np.inf
            else:
                ratio = rate_a / rate_b
            low = 0.0 if ci.low <= 0 else (ci.low / (1.0 - ci.low)) * (n2 / n1)
            high = np.inf if ci.high >= 1 else (ci.high / (1.0 - ci.high)) * (n2 / n1)
            rows.append([k1, k2, n1, n2, rate_a, rate_b, ratio, p, low, high])

        out = make_form(
            np.asarray(rows, dtype=np.float64),
            [feature_dim, "statistic"],
            {feature_dim: {name: i for i, name in enumerate(features)},
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        out.info.update({
            "group_a": group_a,
            "group_b": group_b,
            "alternative": alternative,
            "confidence": confidence,
            "test": "conditional binomial exact",
            "rate_ratio": "rate_a / rate_b",
        })
        ctx[out_name] = out
        self._export_data = {
            "group_a": group_a,
            "group_b": group_b,
            "alternative": alternative,
            "confidence": confidence,
            "n_features": len(features),
        }
        print(f"[poisson_means_test] features={len(features)} groups={group_a}/{group_b}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
