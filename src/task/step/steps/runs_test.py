"""Wald-Wolfowitz runs test for randomness about a threshold."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._stats21_common import numeric_column, table_frame


class RunsTestStep(Step):
    """Runs test with a median (or explicit) threshold."""

    name = "runs_test"
    title = "Runs test"
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
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string"},
            "threshold": {"type": "number"},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "less", "greater"],
                "default": "two-sided",
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
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "runs_test")
        values = numeric_column(frame, value_label, "runs_test")
        values = values[np.isfinite(values)]
        if values.size < 2:
            raise StepError("runs_test: fewer than two finite observations")
        threshold = ctx.step_params.get("threshold")
        if threshold is None:
            threshold = float(np.median(values))
        else:
            threshold = float(threshold)
        above = values > threshold
        below = values < threshold
        keep = above | below
        sequence = above[keep]
        if sequence.size < 2:
            raise StepError("runs_test: fewer than two values differ from threshold")
        n1 = int(sequence.sum())
        n2 = int(sequence.size - n1)
        if n1 == 0 or n2 == 0:
            raise StepError("runs_test: both sides of the threshold need samples")
        runs = 1 + int(np.count_nonzero(sequence[1:] != sequence[:-1]))
        n = n1 + n2
        mean = 1.0 + 2.0 * n1 * n2 / n
        variance = (
            2.0 * n1 * n2 * (2.0 * n1 * n2 - n)
            / (n * n * (n - 1.0))
        )
        if variance <= 0:
            raise StepError("runs_test: runs variance is not positive")
        statistic = float((runs - mean) / np.sqrt(variance))
        alternative = ctx.step_params.get("alternative", "two-sided")
        if alternative == "less":
            p_value = float(stats.norm.cdf(statistic))
        elif alternative == "greater":
            p_value = float(stats.norm.sf(statistic))
        else:
            p_value = float(2.0 * min(stats.norm.cdf(statistic), stats.norm.sf(statistic)))
        p_value = min(max(p_value, 0.0), 1.0)

        out = make_form(
            [
                [statistic],
                [p_value],
                [float(runs)],
                [mean],
                [variance],
                [float(n1)],
                [float(n2)],
                [float(n)],
                [threshold],
            ],
            ["statistic", "value"],
            {
                "statistic": {
                    "statistic": 0,
                    "p": 1,
                    "runs": 2,
                    "expected_runs": 3,
                    "variance": 4,
                    "n1": 5,
                    "n2": 6,
                    "n": 7,
                    "threshold": 8,
                },
                "value": {"value": 0},
            },
        )
        out.info.update(
            {
                "missing_code": np.nan,
                "method": "normal_approximation",
                "alternative": alternative,
                "threshold": threshold,
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic,
            "p": p_value,
            "runs": runs,
            "expected_runs": mean,
            "variance": variance,
            "n1": n1,
            "n2": n2,
            "n": n,
            "threshold": threshold,
            "alternative": alternative,
        }
        print(
            f"[runs_test] runs={runs}, z={statistic:.6f}, p={p_value:.6g}, "
            f"n1={n1}, n2={n2}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
