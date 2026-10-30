"""Mack-Wolfe test for an umbrella alternative with a known peak."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._order_rank_common import align_ordered, finite_groups


class MackWolfeStep(Step):
    """Rank test for a monotone rise to a known peak and fall afterwards.

    The implementation follows ``PMCMRplus::mackWolfeTest`` with a known
    peak. It uses the normal approximation; tie-affected exact variances
    are not available and the R implementation also warns in that case.
    """

    name = "mack_wolfe"
    title = "Mack-Wolfe umbrella test"
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
            "peak": {"type": "string", "title": "峰值组"},
            "group_order": {
                "type": "array",
                "items": {"type": "string"},
                "title": "分组顺序",
            },
            "output": {"type": "string"},
        },
        "required": ["group_label", "peak"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        peak = str(ctx.step_params["peak"])

        values, features, order, indices = align_ordered(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            group_label,
            ctx.step_params.get("group_order"),
            "mack_wolfe",
        )
        if peak not in indices:
            raise StepError(f"mack_wolfe: peak group {peak!r} not found")
        peak_index = order.index(peak)

        rows = []
        kept = []
        for column, feature in enumerate(features):
            groups = finite_groups(values[:, column], indices, order, "mack_wolfe")
            if groups is None:
                continue
            sizes = np.asarray([group.size for group in groups], dtype=np.float64)
            k = len(groups)
            u_matrix = np.zeros((k, k), dtype=np.float64)
            for i in range(1, k):
                for j in range(i):
                    u_matrix[i, j] = float(
                        sum(np.sum(groups[j] > value) for value in groups[i])
                    )
                    u_matrix[j, i] = float(
                        sum(np.sum(groups[i] > value) for value in groups[j])
                    )

            rising = sum(
                u_matrix[i, j]
                for i in range(peak_index)
                for j in range(i + 1, peak_index + 1)
            )
            falling = sum(
                u_matrix[j, i]
                for i in range(peak_index, k - 1)
                for j in range(i + 1, k)
            )
            statistic = float(rising + falling)

            n1 = float(sizes[: peak_index + 1].sum())
            n2 = float(sizes[peak_index:].sum())
            n_total = float(sizes.sum())
            mean = (
                n1 * n1
                + n2 * n2
                - float(np.sum(sizes**2))
                - float(sizes[peak_index] ** 2)
            ) / 4.0
            variance = (
                2.0 * (n1**3 + n2**3)
                + 3.0 * (n1 * n1 + n2 * n2)
                - float(np.sum(sizes**2 * (2.0 * sizes + 3.0)))
                - float(sizes[peak_index] ** 2 * (2.0 * sizes[peak_index] + 3.0))
                + 12.0 * sizes[peak_index] * n1 * n2
                - 12.0 * sizes[peak_index] ** 2 * n_total
            ) / 72.0
            if variance <= 0.0:
                continue
            z_value = (statistic - mean) / np.sqrt(variance)
            p_value = float(stats.norm.sf(z_value))
            rows.append([statistic, float(z_value), p_value, float(k), n_total])
            kept.append(feature)

        if not rows:
            raise StepError("mack_wolfe: no feature had enough finite observations per group")
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: index for index, name in enumerate(kept)},
                "statistic": {
                    "Ap": 0,
                    "z": 1,
                    "p": 2,
                    "n_groups": 3,
                    "n": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Mack-Wolfe",
                "peak": peak,
                "group_order": order,
                "p_method": "normal approximation",
                "ties": "normal variance approximation; exact variance unavailable with ties",
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(order),
            "peak": peak,
            "groups": order,
        }
        print(f"[mack_wolfe] {len(kept)} features, peak={peak}, groups={len(order)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
