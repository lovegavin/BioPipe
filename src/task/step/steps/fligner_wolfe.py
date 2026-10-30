"""Fligner-Wolfe test for a shift against a control group."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._order_rank_common import align_ordered, finite_groups


class FlignerWolfeStep(Step):
    """Rank test comparing every treatment group with a control group.

    The implementation follows ``PMCMRplus::flignerWolfeTest`` with
    ``dist = "Normal"``: the control group is placed first, all values are
    ranked globally, and the control-versus-rest Mann-Whitney statistic is
    standardized with the tie-corrected null variance.
    """

    name = "fligner_wolfe"
    title = "Fligner-Wolfe test"
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
            "control": {"type": "string", "title": "对照组"},
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
        "required": ["group_label", "control"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        control = str(ctx.step_params["control"])
        alternative = ctx.step_params.get("alternative", "greater")

        values, features, order, indices = align_ordered(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            group_label,
            ctx.step_params.get("group_order"),
            "fligner_wolfe",
        )
        if control not in indices:
            raise StepError(f"fligner_wolfe: control group {control!r} not found")
        order = [control] + [group for group in order if group != control]

        rows = []
        kept = []
        for column, feature in enumerate(features):
            groups = finite_groups(values[:, column], indices, order, "fligner_wolfe")
            if groups is None:
                continue
            flat = np.concatenate(groups)
            ranks = stats.rankdata(flat, method="average")
            sizes = np.asarray([group.size for group in groups], dtype=np.float64)
            starts = np.cumsum([0] + [int(size) for size in sizes[:-1]])
            rank_sums = np.asarray(
                [
                    ranks[start : start + int(size)].sum()
                    for start, size in zip(starts, sizes)
                ],
                dtype=np.float64,
            )
            control_n = float(sizes[0])
            treatment_n = float(sizes[1:].sum())
            n_total = float(flat.size)
            statistic = float(rank_sums[1:].sum() - treatment_n * (treatment_n + 1.0) / 2.0)
            counts = np.unique(ranks, return_counts=True)[1]
            ties = counts[counts > 1].astype(np.float64)
            tie_correction = float(np.sum(ties**3 - ties))
            variance = (
                control_n * treatment_n * (n_total + 1.0) / 12.0
                - control_n
                * treatment_n
                / (12.0 * n_total * (n_total - 1.0))
                * tie_correction
            )
            if variance <= 0.0:
                continue
            z_value = (statistic - control_n * treatment_n / 2.0) / np.sqrt(variance)
            if alternative == "greater":
                p_value = float(stats.norm.sf(z_value))
            else:
                p_value = float(stats.norm.cdf(z_value))
            rows.append(
                [
                    float(z_value),
                    p_value,
                    control_n,
                    treatment_n,
                    float(len(groups)),
                    n_total,
                ]
            )
            kept.append(feature)

        if not rows:
            raise StepError("fligner_wolfe: no feature had enough finite observations per group")
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: index for index, name in enumerate(kept)},
                "statistic": {
                    "z": 0,
                    "p": 1,
                    "control_n": 2,
                    "treatment_n": 3,
                    "n_groups": 4,
                    "n": 5,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Fligner-Wolfe",
                "alternative": alternative,
                "control": control,
                "group_order": order,
                "p_method": "normal approximation with tie correction",
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(order),
            "control": control,
            "groups": order,
            "alternative": alternative,
        }
        print(f"[fligner_wolfe] {len(kept)} features, control={control}, groups={len(order)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
