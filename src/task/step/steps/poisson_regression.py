"""Poisson regression for non-negative count outcomes."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._count_common import count_design, result_rows
from ._ext_common import make_form


class PoissonRegressionStep(Step):
    name = "poisson_regression"
    title = "Poisson regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "maxiter": {"type": "integer", "minimum": 1, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        maxiter = int(ctx.step_params.get("maxiter", 200))
        out_name = ctx.step_params.get("output", self.name)

        frame, response, design, terms = count_design(
            inputs[0], sample_dim, feature_dim, response_label, predictors, categorical, self.name
        )
        try:
            result = sm.GLM(response, design, family=sm.families.Poisson()).fit(
                maxiter=maxiter, disp=0
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        rows = result_rows(params, bse, pvalues, conf, terms)
        block = np.asarray(rows, dtype=np.float32)
        ctx[out_name] = make_form(
            block,
            ["term", "statistic"],
            {
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "rate_ratio": 6,
                    "RR_CI_low": 7,
                    "RR_CI_high": 8,
                },
            },
            info={
                "method": "Poisson GLM",
                "n": int(response.size),
                "llf": float(result.llf),
                "aic": float(result.aic),
                "terms": terms,
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in params],
            "se": [float(value) for value in bse],
            "p": [float(value) for value in pvalues],
            "rate_ratio": [float(value) for value in np.exp(params)],
            "llf": float(result.llf),
            "aic": float(result.aic),
            "n": int(response.size),
        }
        print(f"[{self.name}] n={response.size}, terms={len(terms)}")

    def export(self, ctx: Context) -> dict:
        return self._export
