"""Robust linear regression with Huber M-estimation."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._regression30_common import coefficient_rows
from ._stats21_common import design_matrix, numeric_column, table_frame


class RobustRegressionStep(Step):
    """Huber M-estimator matching R MASS::rlm(psi = psi.huber)."""

    name = "robust_regression"
    title = "Robust linear regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
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
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "maxiter": {"type": "integer", "minimum": 1, "default": 100},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.robust.robust_linear_model import RLM

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(
                f"{self.name}: categorical names not in predictors: {missing}"
            )
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(f"{self.name}: response {response_label!r} not found")
        for name in predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")

        valid = np.isfinite(numeric_column(frame, response_label, self.name))
        for name in predictors:
            if name in categorical:
                valid &= frame[name].notna().to_numpy()
            else:
                valid &= np.isfinite(numeric_column(frame, name, self.name))
        frame = frame.loc[valid].reset_index(drop=True)
        response = numeric_column(frame, response_label, self.name)
        if response.size < 4:
            raise StepError(f"{self.name}: fewer than four complete rows")

        design, terms = design_matrix(frame, predictors, categorical, self.name)
        if response.size <= design.shape[1]:
            raise StepError(f"{self.name}: not enough observations for the model")
        maxiter = int(ctx.step_params.get("maxiter", 100))
        try:
            result = RLM(response, design).fit(maxiter=maxiter)
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        rows = coefficient_rows(params, bse, pvalues, conf, terms)
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "t": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                },
            },
            info={
                "method": "Huber M-estimator",
                "scale": float(result.scale),
                "n": int(response.size),
                "df_resid": int(result.df_resid),
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in params],
            "se": [float(value) for value in bse],
            "p": [float(value) for value in pvalues],
            "scale": float(result.scale),
            "n": int(response.size),
            "df_resid": int(result.df_resid),
        }
        print(f"[{self.name}] n={response.size}, terms={len(terms)}")

    def export(self, ctx: Context) -> dict:
        return self._export
