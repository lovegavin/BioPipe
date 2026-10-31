"""Achieved power for a balanced one-way ANOVA."""
from __future__ import annotations

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._power77_common import floating, form, integer


class PowerAnovaStep(Step):
    """Compute achieved power for a balanced one-way ANOVA."""

    name = "power_anova"
    title = "ANOVA power"
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
            "effect_size": {"type": "number", "exclusiveMinimum": 0},
            "n_per_group": {"type": "integer", "minimum": 2},
            "k_groups": {"type": "integer", "minimum": 2},
            "alpha": {"type": "number", "default": 0.05, "exclusiveMinimum": 0, "exclusiveMaximum": 1},
            "output": {"type": "string"},
        },
        "required": ["effect_size", "n_per_group", "k_groups"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.power import FTestAnovaPower

        effect_size = floating(ctx, "effect_size", low=0.0)
        n_per_group = integer(ctx, "n_per_group")
        k_groups = integer(ctx, "k_groups")
        alpha = floating(ctx, "alpha", default=0.05, low=0.0, high=1.0)

        total = n_per_group * k_groups
        power = float(
            FTestAnovaPower().power(
                effect_size=effect_size,
                nobs=total,
                alpha=alpha,
                k_groups=k_groups,
            )
        )
        if not 0.0 <= power <= 1.0:
            raise StepError(f"{self.name}: power is outside [0, 1]")
        df1 = float(k_groups - 1)
        df2 = float(k_groups * (n_per_group - 1))
        rows = [
            ("power", power),
            ("effect_size", effect_size),
            ("n_per_group", float(n_per_group)),
            ("n_total", float(total)),
            ("k_groups", float(k_groups)),
            ("alpha", alpha),
            ("df1", df1),
            ("df2", df2),
        ]
        result = form(
            rows,
            {
                "method": "statsmodels F-test ANOVA power",
                "alternative": "greater",
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = result
        self._export_data = {
            "power": power,
            "effect_size": effect_size,
            "n_per_group": n_per_group,
            "n_total": total,
            "k_groups": k_groups,
            "alpha": alpha,
            "df1": df1,
            "df2": df2,
        }
        print(f"[{self.name}] power={power:.6f}, k={k_groups}, n/group={n_per_group}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
