"""Rainbow test for linearity of a simple linear regression."""
from __future__ import annotations

from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form
from ._regression54_common import ols_rss, rainbow_slice, regression_series


class RainbowTestStep(Step):
    name = "rainbow_test"
    title = "Rainbow test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("variable_dim", "variable")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "variable_dim": {"type": "string", "default": "variable"},
            "response": {"type": "string", "title": "因变量"},
            "regressor": {"type": "string", "title": "自变量"},
            "order_by": {"type": "string", "title": "排序变量（默认自变量）"},
            "fraction": {"type": "number", "default": 0.5, "minimum": 0.0, "exclusiveMaximum": 1.0},
            "center": {"type": "number", "default": 0.5, "minimum": 0.0, "exclusiveMaximum": 1.0},
            "output": {"type": "string"},
        },
        "required": ["response", "regressor"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        variable_dim = ctx.step_params.get("variable_dim", "variable")
        response = ctx.step_params["response"]
        regressor = ctx.step_params["regressor"]
        order_by = ctx.step_params.get("order_by")
        fraction = float(ctx.step_params.get("fraction", 0.5))
        center = float(ctx.step_params.get("center", 0.5))
        out_name = ctx.step_params.get("output", self.name)

        y, x, _ = regression_series(
            form, sample_dim, variable_dim, response, regressor, order_by, self.name
        )
        n = int(y.size)
        from_, to = rainbow_slice(n, fraction, center, self.name)
        n_subset = to - from_ + 1
        if n_subset < 3:
            raise StepError("rainbow_test: central subset needs at least three observations")
        if n_subset >= n:
            raise StepError("rainbow_test: central subset must be smaller than the full sample")
        rss = ols_rss(x, y, self.name)
        rss_subset = ols_rss(x[from_ - 1 : to], y[from_ - 1 : to], self.name)
        df1 = n - n_subset
        df2 = n_subset - 2
        if df1 <= 0 or df2 <= 0:
            raise StepError("rainbow_test: residual degrees of freedom must be positive")
        statistic = float(((rss - rss_subset) / df1) / (rss_subset / df2))
        p_value = float(stats.f.sf(statistic, df1, df2))

        names = ["statistic", "df1", "df2", "p", "n", "subset_n", "from", "to"]
        rows = [statistic, df1, df2, p_value, n, n_subset, from_, to]
        ctx[out_name] = scalar_form(rows, names, "rainbow_test")
        self._export = {
            "statistic": statistic,
            "df1": int(df1),
            "df2": int(df2),
            "p": p_value,
            "n": n,
            "subset_n": n_subset,
            "from": from_,
            "to": to,
            "fraction": fraction,
            "center": center,
            "response": response,
            "regressor": regressor,
            "order_by": order_by or regressor,
        }
        print(f"[rainbow_test] Rain={statistic:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
