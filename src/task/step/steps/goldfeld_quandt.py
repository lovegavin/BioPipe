"""Goldfeld-Quandt test for heteroskedasticity in a simple linear regression."""
from __future__ import annotations

from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form
from ._regression54_common import gq_points, ols_rss, regression_series


class GoldfeldQuandtStep(Step):
    name = "goldfeld_quandt"
    title = "Goldfeld-Quandt test"
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
            "fraction": {"type": "number", "default": 0.0, "minimum": 0.0, "exclusiveMaximum": 0.5},
            "alternative": {
                "type": "string",
                "enum": ["two-sided", "greater", "less"],
                "default": "greater",
            },
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
        fraction = float(ctx.step_params.get("fraction", 0.0))
        alternative = ctx.step_params.get("alternative", "greater")
        out_name = ctx.step_params.get("output", self.name)

        y, x, _ = regression_series(
            form, sample_dim, variable_dim, response, regressor, order_by, self.name
        )
        n = int(y.size)
        point1, point2 = gq_points(n, fraction, self.name)
        rss1 = ols_rss(x[:point1], y[:point1], self.name)
        rss2 = ols_rss(x[point2 - 1 :], y[point2 - 1 :], self.name)
        df1 = n - point2 + 1 - 2
        df2 = point1 - 2
        if df1 <= 0 or df2 <= 0:
            raise StepError("goldfeld_quandt: residual degrees of freedom must be positive")
        statistic = float((rss2 / df1) / (rss1 / df2))
        if alternative == "greater":
            p_value = float(stats.f.sf(statistic, df1, df2))
        elif alternative == "less":
            p_value = float(stats.f.cdf(statistic, df1, df2))
        else:
            p_value = float(min(1.0, 2.0 * min(stats.f.sf(statistic, df1, df2), stats.f.cdf(statistic, df1, df2))))

        names = ["statistic", "df1", "df2", "p", "n", "segment1_n", "segment2_n"]
        rows = [statistic, df1, df2, p_value, n, point1, n - point2 + 1]
        ctx[out_name] = scalar_form(rows, names, "goldfeld_quandt")
        self._export = {
            "statistic": statistic,
            "df1": int(df1),
            "df2": int(df2),
            "p": p_value,
            "n": n,
            "segment1_n": point1,
            "segment2_n": n - point2 + 1,
            "fraction": fraction,
            "alternative": alternative,
            "response": response,
            "regressor": regressor,
            "order_by": order_by or regressor,
        }
        print(f"[goldfeld_quandt] GQ={statistic:.6g} p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
