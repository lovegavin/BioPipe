"""Siegel-Tukey rank dispersion test for two samples."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._tests39_common import select_groups
from ._ext_common import labels_in_order


class SiegelTukeyStep(Step):
    """Siegel-Tukey rank test for equality of dispersion (no ties)."""

    name = "siegel_tukey"
    title = "Siegel-Tukey rank dispersion test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("group_dim", "sample"), param("feature_dim", "feature")]),
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
            "group_a": {"type": ["string", "number"]},
            "group_b": {"type": ["string", "number"]},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "less", "greater"],
                "default": "two-sided",
            },
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        X, codes, _, _, _ = select_groups(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            ctx.step_params["group_label"],
            ctx.step_params["group_a"],
            ctx.step_params["group_b"],
            self.name,
        )
        features = labels_in_order(data, feature_dim)
        rows = []
        kept = []
        exact_flags = []
        for j, feature in enumerate(features):
            x = X[codes == 0, j]
            y = X[codes == 1, j]
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            if x.size < 2 or y.size < 2:
                continue
            result = _siegel(x, y, alternative)
            if result is None:
                continue
            rows.append(result[0])
            exact_flags.append(result[1])
            kept.append(feature)

        if not rows:
            raise StepError(f"{self.name}: no feature had two finite values in each group")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(kept)},
                "statistic": {
                    "W": 0,
                    "p": 1,
                    "n_a": 2,
                    "n_b": 3,
                },
            },
            info={
                "missing_code": np.nan,
                "test": "Siegel-Tukey",
                "alternative": alternative,
                "ties": False,
                "exact": bool(all(exact_flags)),
                "n_features": len(kept),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "test": "Siegel-Tukey",
            "alternative": alternative,
            "exact": bool(all(exact_flags)),
        }
        print(f"[{self.name}] {len(kept)} features")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})



def _siegel(x: np.ndarray, y: np.ndarray, alternative: str):
    m = x.size
    n = y.size
    N = m + n
    combined = np.concatenate([x, y])
    if np.unique(combined).size != N:
        raise StepError(f"siegel_tukey: ties are not supported; got {N - np.unique(combined).size} tied values")
    groups = np.r_[np.zeros(m, dtype=int), np.ones(n, dtype=int)]
    order = np.argsort(combined, kind="mergesort")
    ordered_groups = groups[order]
    ranks = _siegel_ranks(N)
    w = float(np.sum(ranks[ordered_groups == 0]) - m * (m + 1) / 2.0)
    upper, lower, exact = _distribution(m, n, w)
    if alternative == "less":
        p_value = upper
    elif alternative == "greater":
        p_value = lower
    else:
        if w > m * n / 2.0:
            p_value = min(1.0, 2.0 * min(0.5, upper))
        else:
            p_value = min(1.0, 2.0 * min(0.5, lower))
    return [w, float(p_value), float(m), float(n)], exact


def _siegel_ranks(N: int) -> np.ndarray:
    quarters = math.ceil(N / 4)
    a = np.repeat(np.arange(1, quarters + 1), 2)
    b = np.tile([0, 1], quarters)
    up = np.r_[1, a * 4 + b][: (N + 1) // 2]
    down = (a * 4 + b - 2)[: N // 2][::-1]
    return np.r_[up, down]


def _distribution(m: int, n: int, w: float):
    N = m + n
    if m * n > 10000:
        mean = m * n / 2.0
        sd = math.sqrt(m * n * (N + 1) / 12.0)
        z = (w - mean) / sd
        return float(stats.norm.sf(z)), float(stats.norm.cdf(z)), False
    offset = m * (m + 1) // 2
    max_sum = m * n + offset
    dp = [[0] * (max_sum + 1) for _ in range(m + 1)]
    dp[0][0] = 1
    for rank in range(1, N + 1):
        for chosen in range(min(rank, m), 0, -1):
            for total in range(max_sum, rank - 1, -1):
                dp[chosen][total] += dp[chosen - 1][total - rank]
    total_cases = math.comb(N, m)
    lower = sum(dp[m][offset: offset + int(w) + 1]) / total_cases
    upper = sum(dp[m][offset + int(w):]) / total_cases
    return float(upper), float(lower), True
