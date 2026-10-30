"""Moses test of extreme reactions."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class MosesTestStep(Step):
    """Moses two-sample test for extreme reactions."""

    name = "moses_test"
    title = "Moses extreme reactions test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string", "title": "数值字段"},
            "group_label": {"type": "string", "title": "分组字段"},
            "group_a": {"type": "string", "title": "第一组"},
            "group_b": {"type": "string", "title": "第二组"},
            "extreme": {"type": "integer", "minimum": 0, "title": "每侧截尾个数"},
            "output": {"type": "string"},
        },
        "required": ["value_label", "group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        group_label = ctx.step_params["group_label"]
        group_a = str(ctx.step_params["group_a"])
        group_b = str(ctx.step_params["group_b"])
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "moses_test")
        values = numeric_column(frame, value_label, "moses_test")
        if group_label not in frame.columns:
            raise StepError("moses_test: group column not found")
        groups = frame[group_label].to_numpy(dtype=object)
        keep = np.isfinite(values) & np.array([_present(g) for g in groups])
        values, groups = values[keep], groups[keep]
        mask_a = np.array([_key(g) == _key(group_a) for g in groups])
        mask_b = np.array([_key(g) == _key(group_b) for g in groups])
        x = values[mask_a]
        y = values[mask_b]
        n_a, n_b = int(x.size), int(y.size)
        if n_a < 2 or n_b < 2:
            raise StepError("moses_test: each group needs at least two observations")
        h = ctx.step_params.get("extreme")
        if h is None:
            h = max(int(math.floor(0.05 * n_a)), 1)
        h = int(h)
        if 2 * h > n_a - 2:
            h = int(math.floor((n_a - 2) / 2))
        if h < 0 or 2 * h > n_a - 2:
            raise StepError("moses_test: extreme count is too large for group_a")
        combined = np.concatenate([x, y])
        ranks = stats.rankdata(-combined, method="average")[:n_a]
        ranks.sort()
        if h > 0:
            ranks = ranks[h: len(ranks) - h]
        if ranks.size == 0:
            raise StepError("moses_test: no observations remain after trimming")
        s_value = int(math.ceil(float(ranks.max() - ranks.min() + 1.0)))
        upper = s_value - n_a + 2 * h
        total = 0.0
        for i in range(0, upper + 1):
            total += _choose(i + n_a - 2 * h - 2, i) * _choose(n_b + 2 * h + 1 - i, n_b - i)
        denominator = _choose(n_a + n_b, n_a)
        if denominator <= 0:
            raise StepError("moses_test: invalid combinatorial denominator")
        p_value = float(total / denominator)
        if p_value > 1.0:
            p_value = 1.0
        out = scalar_form(
            [float(s_value), p_value, float(n_a), float(n_b), float(h)],
            ["S", "p", "n_a", "n_b", "extreme"],
            "moses_test",
        )
        out.info.update({"alternative": "extreme values are more likely in group_a"})
        ctx[out_name] = out
        self._export_data = {
            "S": s_value, "p": p_value, "n_a": n_a, "n_b": n_b, "extreme": h,
        }
        print(f"[moses_test] S={s_value}, p={p_value:.6g}, n_a={n_a}, n_b={n_b}, h={h}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _choose(n: int, k: int) -> float:
    if n < 0 or k < 0 or k > n:
        return 0.0
    return float(math.comb(n, k))


def _present(value) -> bool:
    if value is None:
        return False
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return str(value).strip() not in {"", "nan", "None"}


def _key(value) -> str:
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return str(value)
