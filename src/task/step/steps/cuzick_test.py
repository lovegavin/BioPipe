"""Cuzick rank trend test for ordered groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_map, labels_in_order, make_form, reorder


class CuzickTestStep(Step):
    """Cuzick's rank-based trend test across ordered groups.

    Groups are ordered by their encoded group code (the order in which labels
    first appear in the metadata). ``group_scores`` can override the default
    ``1..k`` scores; it must follow that same group order.
    """

    name = "cuzick_test"
    title = "Cuzick trend test"
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
            "group_scores": {"type": "array", "items": {"type": "number"}},
            "alternative": {
                "type": "string",
                "enum": ["two.sided", "greater", "less"],
                "default": "two.sided",
            },
            "continuity": {"type": "boolean", "default": False},
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
        alternative = ctx.step_params.get("alternative", "two.sided")
        continuity = bool(ctx.step_params.get("continuity", False))

        matrix = reorder(data, sample_dim, feature_dim)
        samples = labels_in_order(data, sample_dim)
        features = labels_in_order(data, feature_dim)
        meta_samples, codes = group_map(meta, group_dim, group_label)
        meta_pos = {name: i for i, name in enumerate(meta_samples)}
        keep = [i for i, name in enumerate(samples) if name in meta_pos]
        if len(keep) < 4:
            raise StepError("cuzick_test: need at least four shared samples")
        matrix = matrix[keep]
        codes = codes[[meta_pos[samples[i]] for i in keep]]
        groups = sorted(set(int(code) for code in codes))
        if len(groups) < 2:
            raise StepError("cuzick_test: need at least two groups")
        for group in groups:
            if int(np.sum(codes == group)) < 2:
                raise StepError(f"cuzick_test: group {group} has fewer than two samples")

        scores_arg = ctx.step_params.get("group_scores")
        k = len(groups)
        if scores_arg is None:
            scores = np.arange(1.0, k + 1.0)
        else:
            scores = np.asarray(scores_arg, dtype=np.float64)
            if scores.size != k:
                raise StepError("cuzick_test: group_scores must have one value per group")
            if not np.all(np.isfinite(scores)):
                raise StepError("cuzick_test: group_scores must be finite")
        if np.all(scores == scores[0]):
            raise StepError("cuzick_test: group_scores must not all be equal")

        rows = []
        row_labels = []
        for column, feature in enumerate(features):
            values = []
            for group in groups:
                value = matrix[codes == group, column]
                value = value[np.isfinite(value)]
                if value.size == 0:
                    values = []
                    break
                values.append(value)
            if len(values) < 2:
                continue
            sizes = np.asarray([value.size for value in values], dtype=np.float64)
            total = float(sizes.sum())
            if total < 2:
                continue
            ranks = stats.rankdata(np.concatenate(values), method="average")
            starts = np.cumsum([0] + [int(size) for size in sizes[:-1]])
            rank_sums = np.asarray(
                [
                    ranks[start : start + int(size)].sum()
                    for start, size in zip(starts, sizes)
                ],
                dtype=np.float64,
            )
            t_value = float(np.sum(rank_sums * scores))
            l_value = float(np.sum(sizes * scores))
            expected = l_value * (total + 1.0) / 2.0
            variance = (total + 1.0) / 12.0 * (
                total * float(np.sum(scores**2 * sizes)) - l_value**2
            )
            if variance <= 0.0:
                continue
            difference = t_value - expected
            if continuity:
                if difference > 0:
                    difference -= 0.5
                elif difference < 0:
                    difference += 0.5
            z_value = float(difference / np.sqrt(variance))
            if alternative == "greater":
                p_value = float(stats.norm.sf(z_value))
            elif alternative == "less":
                p_value = float(stats.norm.cdf(z_value))
            else:
                p_value = float(2.0 * min(stats.norm.sf(abs(z_value)), 0.5))
            rows.append([z_value, p_value, t_value, total, float(k)])
            row_labels.append(feature)

        if not rows:
            raise StepError("cuzick_test: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = make_form(
            rows,
            ["feature", "statistic"],
            {
                "feature": {name: i for i, name in enumerate(row_labels)},
                "statistic": {
                    "z": 0,
                    "p": 1,
                    "T": 2,
                    "n": 3,
                    "n_groups": 4,
                },
            },
            {
                "method": "Cuzick",
                "alternative": alternative,
                "tie_correction": False,
                "scores": [float(value) for value in scores],
            },
        )
        self._export_data = {
            "n_features": len(features),
            "n_tested": len(rows),
            "n_groups": k,
            "scores": [float(value) for value in scores],
            "alternative": alternative,
        }
        print(f"[cuzick_test] {len(rows)} features, {k} ordered groups")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
