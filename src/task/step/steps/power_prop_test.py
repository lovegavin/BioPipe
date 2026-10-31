"""Achieved power for a two-sample difference in proportions."""
from __future__ import annotations

import math

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._power77_common import floating, form, integer


class PowerPropTestStep(Step):
    """Compute achieved power for a two-sided two-proportion test."""

    name = "power_prop_test"
    title = "Two-proportion power"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 0
    outputs = []
    output_parameter = "output"
    input_contracts = []
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "p1": {"type": "number", "minimum": 0, "maximum": 1},
            "p2": {"type": "number", "minimum": 0, "maximum": 1},
            "nobs1": {"type": "integer", "minimum": 2},
            "nobs2": {"type": "integer", "minimum": 2},
            "alpha": {"type": "number", "default": 0.05, "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            "output": {"type": "string"},
        },
        "required": ["p1", "p2", "nobs1", "nobs2"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.power import NormalIndPower

        p1 = floating(ctx, "p1")
        p2 = floating(ctx, "p2")
        if not 0.0 <= p1 <= 1.0 or not 0.0 <= p2 <= 1.0:
            raise StepError(f"{self.name}: p1 and p2 must be in [0, 1]")
        nobs1 = integer(ctx, "nobs1")
        nobs2 = integer(ctx, "nobs2")
        alpha = floating(ctx, "alpha", default=0.05, low=0.0, high=1.0)

        effect = 2.0 * math.asin(math.sqrt(p1)) - 2.0 * math.asin(math.sqrt(p2))
        if abs(effect) < 1e-15:
            raise StepError(f"{self.name}: p1 and p2 must differ")
        power = float(
            NormalIndPower().power(
                effect_size=abs(effect),
                nobs1=nobs1,
                alpha=alpha,
                ratio=float(nobs2) / float(nobs1),
                alternative="two-sided",
            )
        )
        if not 0.0 <= power <= 1.0:
            raise StepError(f"{self.name}: power is outside [0, 1]")
        rows = [
            ("power", power),
            ("effect_size", effect),
            ("p1", p1),
            ("p2", p2),
            ("nobs1", float(nobs1)),
            ("nobs2", float(nobs2)),
            ("alpha", alpha),
        ]
        result = form(
            rows,
            {
                "method": "Cohen h with normal approximation",
                "alternative": "two-sided",
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = result
        self._export_data = {
            "power": power,
            "effect_size": effect,
            "p1": p1,
            "p2": p2,
            "nobs1": nobs1,
            "nobs2": nobs2,
            "alpha": alpha,
        }
        print(f"[{self.name}] power={power:.6f}, h={effect:.6f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
