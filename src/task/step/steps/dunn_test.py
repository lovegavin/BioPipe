"""Dunn's pairwise post-hoc test after Kruskal-Wallis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import correct
from ._matrix_common import grouped


class DunnTestStep(Step):
    """Pairwise Dunn comparisons with tie correction."""

    name = "dunn_test"
    title = "Dunn post-hoc test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11", "statsmodels>=0.14"]
    dependency_imports = ["scipy", "statsmodels"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
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
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "method": {
                "type": "string",
                "enum": ["holm", "fdr", "bonferroni", "none"],
                "default": "holm",
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
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            ctx.step_params["group_label"],
        )
        method = ctx.step_params.get("method", "holm")
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = np.asarray([col[:, i] for col in columns], dtype=np.float64)
            values = [v[np.isfinite(v)] for v in values]
            if any(len(v) == 0 for v in values):
                continue
            all_values = np.concatenate(values)
            n = len(all_values)
            if n < 4:
                continue
            ranks = stats.rankdata(all_values, method="average")
            counts = np.bincount(ranks.astype(int))
            tie_sum = float(np.sum(counts**3 - counts))
            offset = n * (n + 1) / 12.0
            if n > 1:
                offset -= tie_sum / (12.0 * (n - 1))
            if offset <= 0:
                continue
            starts = np.cumsum([0] + [len(v) for v in values[:-1]])
            mean_ranks = [float(ranks[s:s + len(v)].mean()) for s, v in zip(starts, values)]
            pair_rows = []
            for a in range(len(values)):
                for b in range(a + 1, len(values)):
                    denom = np.sqrt(
                        offset * (1.0 / len(values[a]) + 1.0 / len(values[b]))
                    )
                    if denom <= 0:
                        continue
                    z = (mean_ranks[a] - mean_ranks[b]) / denom
                    p = float(stats.norm.sf(abs(z)))
                    pair_rows.append(
                        (
                            f"{feature}: {groups[a]} vs {groups[b]}",
                            float(z),
                            p,
                            mean_ranks[a],
                            mean_ranks[b],
                            float(len(values[a])),
                            float(len(values[b])),
                        )
                    )
            if not pair_rows:
                continue
            pvals = np.asarray([row[2] for row in pair_rows], dtype=np.float64)
            adjusted = (
                correct(pvals, method) if method != "none" else pvals
            )
            for row, padj in zip(pair_rows, adjusted):
                comparisons.append(row[0])
                rows.append(
                    [
                        row[1],
                        row[2],
                        float(padj),
                        row[3],
                        row[4],
                        row[5],
                        row[6],
                    ]
                )

        if not rows:
            raise StepError("dunn_test: no feature had enough finite group data")
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {
                    "z": 0,
                    "P": 1,
                    "P_adj": 2,
                    "mean_rank_a": 3,
                    "mean_rank_b": 4,
                    "n_a": 5,
                    "n_b": 6,
                },
            },
            info={"missing_code": np.nan, "method": method},
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
            "method": method,
        }
        print(
            f"[dunn_test] {len(features)} features, "
            f"{len(comparisons)} comparisons, method={method}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
