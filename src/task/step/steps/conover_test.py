"""Conover post-hoc pairwise comparisons after Kruskal-Wallis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped


def _adjust(pvalues: np.ndarray, method: str) -> np.ndarray:
    pvalues = np.asarray(pvalues, dtype=np.float64)
    m = pvalues.size
    if m == 0 or method == "none":
        return pvalues.copy()
    order = np.argsort(pvalues, kind="mergesort")
    ranked = pvalues[order]
    if method == "bonferroni":
        adjusted = ranked * m
    elif method == "holm":
        adjusted = np.maximum.accumulate((m - np.arange(m)) * ranked)
    elif method in {"BH", "fdr", "BY"}:
        factor = 1.0
        if method == "BY":
            factor = float(np.sum(1.0 / np.arange(1, m + 1)))
        adjusted = ranked * m * factor / np.arange(1, m + 1)
        adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    else:  # pragma: no cover - schema restricts this
        raise StepError(f"unsupported p-value adjustment: {method}")
    adjusted = np.clip(adjusted, 0.0, 1.0)
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


class ConoverTestStep(Step):
    """All-pairwise Conover comparisons for every feature.

    Mean-rank differences are tested with the Conover variance correction
    after Kruskal-Wallis, matching ``DescTools::ConoverTest``.
    """

    name = "conover_test"
    title = "Conover post-hoc test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
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
            "method": {
                "type": "string",
                "enum": ["holm", "bonferroni", "BH", "BY", "fdr", "none"],
                "default": "holm",
            },
            "alternative": {
                "type": "string",
                "enum": ["two.sided", "less", "greater"],
                "default": "two.sided",
            },
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("conover_test needs at least two groups")
        method = ctx.step_params.get("method", "holm")
        alternative = ctx.step_params.get("alternative", "two.sided")
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = []
            for col in columns:
                value = np.asarray(col[:, i], dtype=np.float64)
                value = value[np.isfinite(value)]
                if value.size < 2:
                    values = []
                    break
                values.append(value)
            if len(values) < 2:
                continue
            sizes = np.asarray([value.size for value in values], dtype=np.float64)
            n_total = int(sizes.sum())
            k = len(values)
            if n_total <= k:
                continue
            ranks = stats.rankdata(np.concatenate(values), method="average")
            starts = np.cumsum([0] + [int(size) for size in sizes[:-1]])
            rank_sums = np.asarray(
                [ranks[start:start + int(size)].sum() for start, size in zip(starts, sizes)],
                dtype=np.float64,
            )
            mean_ranks = rank_sums / sizes
            h_value = (
                12.0 / (n_total * (n_total + 1.0)) * float(np.sum(rank_sums**2 / sizes))
                - 3.0 * (n_total + 1.0)
            )
            counts = np.unique(ranks, return_counts=True)[1]
            ties = counts[counts > 1].astype(np.float64)
            ties_adjust = 1.0 - float(np.sum(ties**3 - ties)) / (n_total**3 - n_total)
            if ties_adjust == 1.0:
                s2 = n_total * (n_total + 1.0) / 12.0
            else:
                s2 = (
                    float(np.sum(ranks**2))
                    - n_total * ((n_total + 1.0) ** 2) / 4.0
                ) / (n_total - 1.0)
            factor = (n_total - 1.0 - h_value / ties_adjust) / (n_total - k)
            if s2 <= 0.0 or factor <= 0.0:
                continue
            raw = []
            local = []
            for b in range(1, k):
                for a in range(b):
                    diff = float(mean_ranks[a] - mean_ranks[b])
                    stderr = np.sqrt(s2 * factor * (1.0 / sizes[a] + 1.0 / sizes[b]))
                    if stderr <= 0.0:
                        continue
                    stat = diff / stderr
                    if alternative == "less":
                        p_value = float(stats.t.cdf(abs(stat), n_total - k))
                    elif alternative == "greater":
                        p_value = float(stats.t.sf(abs(stat), n_total - k))
                    else:
                        p_value = float(2.0 * stats.t.sf(abs(stat), n_total - k))
                    raw.append(p_value)
                    local.append([
                        diff,
                        stat,
                        p_value,
                        mean_ranks[a],
                        mean_ranks[b],
                        sizes[a],
                        sizes[b],
                        a,
                        b,
                    ])
            if not raw:
                continue
            adjusted = _adjust(np.asarray(raw), method)
            for values_row, p_adj in zip(local, adjusted):
                key = f"{feature}: {groups[int(values_row[7])]} vs {groups[int(values_row[8])]}"
                comparisons.append(key)
                rows.append(values_row[:2] + [float(p_adj)] + values_row[3:7])

        if not rows:
            raise StepError("conover_test: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {
                    "rank_diff": 0,
                    "statistic": 1,
                    "p": 2,
                    "mean_rank_a": 3,
                    "mean_rank_b": 4,
                    "n_a": 5,
                    "n_b": 6,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Conover",
                "adjustment": method,
                "alternative": alternative,
            },
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
            "adjustment": method,
        }
        print(f"[conover_test] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
