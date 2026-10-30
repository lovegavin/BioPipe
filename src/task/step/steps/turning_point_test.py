"""Turning point test for serial randomness."""
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


class TurningPointTestStep(Step):
    """Turning point test for serial randomness.

    Counts local maxima/minima in the observed order. Under randomness,
    ``E[T] = 2(n-2)/3`` and ``Var[T] = (16n-29)/90``; the two-sided
    normal p-value matches ``randtests::turning.point.test``.
    """

    name = "turning_point_test"
    title = "Turning point randomness test"
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
        frame = table_frame(form, sample_dim, feature_dim, "turning_point_test")
        values = numeric_column(frame, value_label, "turning_point_test")
        values = np.asarray(values, dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 4:
            raise StepError("turning_point_test: need at least four observations")
        differences = np.diff(values)
        if np.any(differences == 0):
            raise StepError("turning_point_test: consecutive ties are not supported")
        turns = int(np.sum(differences[:-1] * differences[1:] < 0))
        expected = 2.0 * (n - 2) / 3.0
        variance = (16.0 * n - 29.0) / 90.0
        if variance <= 0:
            raise StepError("turning_point_test: invalid normal-approximation variance")
        z_value = float((turns - expected) / math.sqrt(variance))
        p_value = float(2.0 * stats.norm.sf(abs(z_value)))
        out = scalar_form(
            [float(turns), z_value, expected, variance, p_value, float(n)],
            ["turns", "z", "expected", "variance", "p", "n"],
            "turning_point_test",
        )
        out.info.update({"alternative": "two-sided non-randomness"})
        ctx[out_name] = out
        self._export_data = {
            "turns": turns, "z": z_value, "expected": expected,
            "variance": variance, "p": p_value, "n": n,
        }
        print(f"[turning_point_test] turns={turns}, z={z_value:.6f}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
