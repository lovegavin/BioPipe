"""Harvey-Collier linearity test for an OLS regression."""
from __future__ import annotations

from statsmodels.stats.diagnostic import linear_harvey_collier

from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._diagnostics29_common import fit_linear
from ._ext_common import make_form


class HarveyCollierStep(Step):
    name = "harvey_collier"
    title = "Harvey-Collier linearity test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": False,
            "axis_info_open": False,
            "info": {"missing_code": {"type": ["number", "null"]}},
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        out_name = ctx.step_params.get("output", self.name)
        result, _, _, _ = fit_linear(
            inputs[0], sample_dim, feature_dim, response_label, predictors, categorical, self.name
        )
        test = linear_harvey_collier(result)
        rows = [
            ("statistic", float(test.statistic)),
            ("p", float(test.pvalue)),
            ("df", float(test.df)),
        ]
        ctx[out_name] = make_form(
            [[value] for _, value in rows],
            ["statistic", "value"],
            {
                "statistic": {name: i for i, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
        )
        self._export = {
            "statistic": float(test.statistic),
            "p": float(test.pvalue),
            "df": int(test.df),
        }
        print(f"[{self.name}] t={test.statistic:.4f}, p={test.pvalue:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
