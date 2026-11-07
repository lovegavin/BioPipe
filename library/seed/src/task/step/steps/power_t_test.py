"""Achieved power for one- and two-sample t tests."""
from __future__ import annotations

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._power77_common import alternative, floating, form, integer


class PowerTTestStep(Step):
    provider = 'operon-core'
    """Compute achieved power for a t test from effect size and sample size."""
    parameters_file = 'power_t_test.PowerTTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'power_t_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 't-test power',
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
     'description': 'Compute achieved power for a t test from effect size and sample size.'}


    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.power import TTestIndPower, TTestPower

        test = str(ctx.step_params.get("test", "two-sample"))
        if test not in {"two-sample", "paired", "one-sample"}:
            raise StepError(f"{self.name}: test must be two-sample, paired, or one-sample")
        effect_size = floating(ctx, "effect_size", low=0.0)
        alpha = floating(ctx, "alpha", default=0.05, low=0.0, high=1.0)
        nobs1 = integer(ctx, "nobs1")
        alt = alternative(ctx)
        statsmodels_alt = {
            "two-sided": "two-sided",
            "greater": "larger",
            "less": "smaller",
        }[alt]

        if test == "two-sample":
            nobs2 = ctx.step_params.get("nobs2")
            if nobs2 is None:
                ratio = floating(ctx, "ratio", default=1.0, low=0.0)
                nobs2_value = float(nobs1) * ratio
            else:
                nobs2_value = float(integer(ctx, "nobs2"))
                ratio = nobs2_value / float(nobs1)
            power = float(
                TTestIndPower().power(
                    effect_size=effect_size,
                    nobs1=nobs1,
                    alpha=alpha,
                    ratio=ratio,
                    alternative=statsmodels_alt,
                )
            )
            df = float(nobs1) + nobs2_value - 2.0
        else:
            ratio = 1.0
            nobs2_value = float(nobs1)
            power = float(
                TTestPower().power(
                    effect_size=effect_size,
                    nobs=nobs1,
                    alpha=alpha,
                    alternative=statsmodels_alt,
                )
            )
            df = float(nobs1 - 1)

        if not 0.0 <= power <= 1.0:
            raise StepError(f"{self.name}: power is outside [0, 1]")
        rows = [
            ("power", power),
            ("effect_size", effect_size),
            ("nobs1", float(nobs1)),
            ("nobs2", nobs2_value),
            ("alpha", alpha),
            ("df", df),
        ]
        info = {
            "method": "statsmodels t-test power",
            "test": test,
            "alternative": alt,
            "ratio": ratio,
        }
        result = form(rows, info)
        ctx[ctx.step_params.get("output", self.name)] = result
        self._export_data = {
            "power": power,
            "effect_size": effect_size,
            "nobs1": nobs1,
            "nobs2": nobs2_value,
            "alpha": alpha,
            "df": df,
            "test": test,
            "alternative": alt,
        }
        print(f"[{self.name}] power={power:.6f}, test={test}, n1={nobs1}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
