"""Achieved power for a two-sample difference in proportions."""
from __future__ import annotations

import math

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._power77_common import floating, form, integer


class PowerPropTestStep(Step):
    provider = 'operon-core'
    """Compute achieved power for a two-sided two-proportion test."""
    parameters_file = 'power_prop_test.PowerPropTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'power_prop_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Two-proportion power',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 0,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Compute achieved power for a two-sided two-proportion test.'}


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
