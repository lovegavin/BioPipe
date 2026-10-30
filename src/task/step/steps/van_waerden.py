"""Van der Waerden normal-scores test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._tests39_common import select_groups


class VanWaerdenStep(Step):
    """Two-sample Van der Waerden normal-scores test.

    Matches ``DescTools::VanWaerdenTest``: normal scores are
    ``qnorm(rank/(n+1))`` and the statistic is
    ``(n-1)/sum(z^2) * sum((sum_g z)^2/n_g)`` with a chi-square p-value.
    """

    name = "van_waerden"
    title = "Van der Waerden test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "label")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "label"},
            "group_label": {"type": "string", "title": "分组字段"},
            "group_a": {"type": "string", "title": "A 组"},
            "group_b": {"type": "string", "title": "B 组"},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        group_dim = ctx.step_params.get("group_dim", "label")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        out_name = ctx.step_params.get("output", self.name)
        data, codes, kept, a_key, b_key = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            group_label, group_a, group_b, "van_waerden",
        )
        statistic = 0.0
        p_value = 0.0
        n_total = 0
        n_a = 0
        n_b = 0
        for j in range(data.shape[1]):
            values = np.asarray(data[:, j], dtype=np.float64)
            keep = np.isfinite(values)
            values = values[keep]
            local_codes = codes[keep]
            if int((local_codes == 0).sum()) < 2 or int((local_codes == 1).sum()) < 2:
                raise StepError("van_waerden: each group needs at least two finite values")
            ranks = stats.rankdata(values, method="average")
            scores = stats.norm.ppf(ranks / (len(values) + 1.0))
            denom = float(np.sum(scores * scores))
            if denom <= 0 or not np.isfinite(denom):
                raise StepError("van_waerden: normal scores have zero variance")
            numerator = 0.0
            for code in (0, 1):
                group_scores = scores[local_codes == code]
                numerator += float(np.sum(group_scores) ** 2) / group_scores.size
            statistic = float((len(values) - 1.0) * numerator / denom)
            p_value = float(stats.chi2.sf(statistic, 1))
            n_total = int(len(values))
            n_a = int((local_codes == 0).sum())
            n_b = int((local_codes == 1).sum())

        out = scalar_form(
            [statistic, 1.0, p_value, float(n_total), float(n_a), float(n_b)],
            ["statistic", "df", "p", "n", "n_a", "n_b"],
            "van_waerden",
        )
        out.info.update({"groups": [a_key, b_key], "method": "normal scores"})
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "df": 1, "p": p_value,
            "n": n_total, "n_a": n_a, "n_b": n_b, "groups": [a_key, b_key],
        }
        print(f"[van_waerden] chi2={statistic:.6f}, p={p_value:.6g}, n={n_total}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
