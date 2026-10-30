"""Chacko's test for an ordered alternative across groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._order_rank_common import align_ordered, finite_groups, pava


class ChackoTestStep(Step):
    """Rank-based test for a monotone ordered alternative.

    The statistic follows ``PMCMRplus::chackoTest``: global ranks are
    averaged by group, pooled by weighted PAVA, and compared with the
    average rank under the null. The p-value uses the chi-square
    approximation with ``k - 1`` degrees of freedom.
    """

    name = "chacko_test"
    title = "Chacko ordered alternatives test"
    category = "Statistics"
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
            "group_order": {
                "type": "array",
                "items": {"type": "string"},
                "title": "分组顺序",
            },
            "alternative": {
                "type": "string",
                "enum": ["greater", "less"],
                "default": "greater",
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
        group_label = ctx.step_params["group_label"]
        alternative = ctx.step_params.get("alternative", "greater")

        values, features, order, indices = align_ordered(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            group_label,
            ctx.step_params.get("group_order"),
            "chacko_test",
        )
        rows = []
        kept = []
        for column, feature in enumerate(features):
            groups = finite_groups(values[:, column], indices, order, "chacko_test")
            if groups is None:
                continue
            flat = np.concatenate(groups)
            ranks = stats.rankdata(flat, method="average")
            sizes = np.asarray([group.size for group in groups], dtype=np.float64)
            starts = np.cumsum([0] + [int(size) for size in sizes[:-1]])
            rank_means = np.asarray(
                [
                    ranks[start : start + int(size)].mean()
                    for start, size in zip(starts, sizes)
                ],
                dtype=np.float64,
            )
            isotropic = pava(rank_means, sizes, increasing=alternative == "greater")
            n_total = float(flat.size)
            expected = (n_total + 1.0) / 2.0
            statistic = (
                12.0
                / (n_total * (n_total + 1.0))
                * float(np.sum(sizes * (isotropic - expected) ** 2))
            )
            df = len(groups) - 1
            p_value = float(stats.chi2.sf(statistic, df))
            rows.append([statistic, float(df), p_value, n_total, float(len(groups))])
            kept.append(feature)

        if not rows:
            raise StepError("chacko_test: no feature had enough finite observations per group")
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: index for index, name in enumerate(kept)},
                "statistic": {
                    "H": 0,
                    "df": 1,
                    "p": 2,
                    "n": 3,
                    "n_groups": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Chacko",
                "alternative": alternative,
                "group_order": order,
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(order),
            "groups": order,
            "alternative": alternative,
        }
        print(f"[chacko_test] {len(kept)} features, {len(order)} groups")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
