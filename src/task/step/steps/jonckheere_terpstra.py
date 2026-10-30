"""Jonckheere-Terpstra test for an ordered alternative."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


def _key(value) -> str:
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return str(number)
    return str(value)


def _natural_groups(values: list[str]) -> list[str]:
    unique = list(dict.fromkeys(values))
    try:
        return sorted(unique, key=float)
    except (TypeError, ValueError):
        return sorted(unique)


class JonckheereTerpstraStep(Step):
    """Rank-based test for a monotone trend across ordered groups.

    The p-value uses the normal approximation, matching
    ``DescTools::JonckheereTerpstraTest(..., exact=FALSE)``. Ties are
    preserved in the statistic but the normal variance does not include a
    tie correction (the same convention as the R implementation).
    """

    name = "jonckheere_terpstra"
    title = "Jonckheere-Terpstra test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string", "title": "数值字段"},
            "group_label": {"type": "string", "title": "分组字段"},
            "group_order": {
                "type": "array",
                "items": {"type": "string"},
                "title": "分组顺序",
            },
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "increasing", "decreasing"],
                "default": "two-sided",
                "title": "备择假设",
            },
            "output": {"type": "string"},
        },
        "required": ["value_label", "group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        group_label = ctx.step_params["group_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "jonckheere_terpstra")
        if value_label not in frame.columns:
            raise StepError(f"jonckheere_terpstra: value column {value_label!r} not found")
        if group_label not in frame.columns:
            raise StepError(f"jonckheere_terpstra: group column {group_label!r} not found")
        values = numeric_column(frame, value_label, "jonckheere_terpstra")
        raw_groups = [_key(value) for value in frame[group_label].tolist()]
        keep = np.isfinite(values) & np.array([bool(value) and value != "None" for value in raw_groups])
        values = values[keep]
        groups = [group for group, flag in zip(raw_groups, keep) if flag]
        if len(values) < 2:
            raise StepError("jonckheere_terpstra: at least two observations are required")

        requested = ctx.step_params.get("group_order")
        if requested:
            order = [_key(value) for value in requested]
            if len(set(order)) != len(order):
                raise StepError("jonckheere_terpstra: group_order contains duplicates")
            unknown = sorted(set(groups) - set(order))
            if unknown:
                raise StepError(
                    f"jonckheere_terpstra: group_order does not cover observed groups {unknown}"
                )
            order = [group for group in order if group in set(groups)]
        else:
            order = _natural_groups(groups)
        if len(order) < 2:
            raise StepError("jonckheere_terpstra: at least two groups are required")

        by_group = [[float(value) for value, group in zip(values, groups) if group == name] for name in order]
        if any(not group for group in by_group):
            raise StepError("jonckheere_terpstra: every ordered group must contain observations")
        sizes = [len(group) for group in by_group]
        n = len(values)
        cumulative = np.concatenate(([0], np.cumsum(sizes)))
        sorted_values = np.concatenate([np.asarray(group, dtype=np.float64) for group in by_group])
        jt_sum = 0.0
        jt_mean = 0.0
        jt_var = 0.0
        for index in range(len(order) - 1):
            na = sizes[index]
            nb = n - int(cumulative[index + 1])
            segment = sorted_values[int(cumulative[index]) :]
            ranks = stats.rankdata(segment, method="average")
            jt_sum += float(np.sum(ranks[:na]) - na * (na + 1) / 2.0)
            jt_mean += na * nb / 2.0
            jt_var += na * nb * (na + nb + 1) / 12.0
        statistic = 2.0 * jt_mean - jt_sum
        if jt_var <= 0:
            raise StepError("jonckheere_terpstra: test variance is zero")
        z_value = (statistic - jt_mean) / np.sqrt(jt_var)
        lower = float(stats.norm.cdf(z_value))
        if alternative == "increasing":
            p_value = 1.0 - lower
        elif alternative == "decreasing":
            p_value = lower
        else:
            p_value = 2.0 * min(lower, 1.0 - lower, 1.0)
        p_value = float(np.clip(p_value, 0.0, 1.0))

        out = scalar_form(
            [statistic, float(z_value), p_value, float(n), float(len(order)), jt_mean, jt_var],
            ["statistic", "z", "p", "n", "n_groups", "mean", "variance"],
            "jonckheere_terpstra",
        )
        out.info.update(
            {
                "groups": order,
                "group_sizes": sizes,
                "alternative": alternative,
                "p_method": "normal approximation (no tie correction)",
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": float(statistic),
            "z": float(z_value),
            "p": p_value,
            "n": int(n),
            "n_groups": len(order),
            "mean": float(jt_mean),
            "variance": float(jt_var),
            "groups": order,
            "group_sizes": sizes,
            "alternative": alternative,
        }
        print(
            f"[jonckheere_terpstra] JT={statistic:.6f}, z={z_value:.6f}, "
            f"p={p_value:.6g}, n={n}, groups={len(order)}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
