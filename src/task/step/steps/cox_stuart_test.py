"""Cox-Stuart test for monotone trend."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class CoxStuartTestStep(Step):
    """Cox-Stuart sign test for a monotone trend.

    The series is split into two halves after dropping the middle value of an
    odd-length series. Discordant pairs (second value greater than the first)
    are counted and compared with ``Binomial(n_pairs, 0.5)``; tied pairs are
    excluded from the binomial sample size, matching
    ``randtests::cox.stuart.test``.
    """

    name = "cox_stuart_test"
    title = "Cox-Stuart trend test"
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
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "increasing", "decreasing"],
                "default": "two-sided",
                "title": "备择假设",
            },
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "cox_stuart_test")
        values = np.asarray(numeric_column(frame, value_label, "cox_stuart_test"), dtype=np.float64)
        values = values[np.isfinite(values)]
        n_original = int(values.size)
        if n_original < 2:
            raise StepError("cox_stuart_test: need at least two observations")
        if n_original % 2 == 1:
            values = np.delete(values, n_original // 2)
        half = values.size // 2
        first = values[:half]
        second = values[half:]
        n_pairs = int(half)
        if n_pairs < 1:
            raise StepError("cox_stuart_test: need at least one pair")
        differences = second - first
        n = int(np.count_nonzero(differences))
        ties = n_pairs - n
        successes = int(np.count_nonzero(differences > 0))

        if alternative == "increasing":
            p_value = float(stats.binom.sf(successes - 1, n, 0.5)) if n else 1.0
            alt_text = "increasing trend"
        elif alternative == "decreasing":
            p_value = float(stats.binom.cdf(successes, n, 0.5)) if n else 1.0
            alt_text = "decreasing trend"
        else:
            if n:
                lower = float(stats.binom.cdf(successes, n, 0.5))
                upper = float(stats.binom.sf(successes - 1, n, 0.5))
                p_value = min(1.0, 2.0 * min(lower, upper))
            else:
                p_value = 1.0
            alt_text = "non-randomness"
        p_value = min(max(p_value, 0.0), 1.0)

        out = scalar_form(
            [float(successes), p_value, float(n), float(n_pairs), float(ties)],
            ["t", "p", "n", "n_pairs", "ties"],
            "cox_stuart_test",
        )
        out.info.update({"alternative": alt_text, "method": "Cox-Stuart sign test"})
        ctx[out_name] = out
        self._export_data = {
            "t": successes, "p": p_value, "n": n, "n_pairs": n_pairs,
            "ties": ties, "alternative": alternative,
        }
        print(f"[cox_stuart_test] t={successes}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
