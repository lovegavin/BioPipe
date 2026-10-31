"""Inverse Gaussian GLM regression for positive continuous responses."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class InverseGaussianRegressionStep(Step):
    """Inverse Gaussian GLM with a log link, fitted by maximum likelihood."""

    name = "inverse_gaussian_regression"
    title = "Inverse Gaussian regression"
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
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
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
        confidence = float(ctx.step_params.get("confidence", 0.95))
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(f"{self.name}: categorical names not in predictors: {missing}")
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(f"{self.name}: response {response_label!r} not found")
        for name in predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")

        y = numeric_column(frame, response_label, self.name)
        design, terms = design_matrix(frame, predictors, categorical, self.name)
        keep = np.isfinite(y) & np.isfinite(design).all(axis=1)
        y = y[keep]
        design = design[keep]
        if np.any(y <= 0):
            raise StepError(f"{self.name}: response must be strictly positive")
        if y.size <= design.shape[1] + 2:
            raise StepError(f"{self.name}: not enough observations")
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: design matrix is rank deficient")

        family = sm.families.InverseGaussian(link=sm.families.links.Log())
        try:
            result = sm.GLM(y, design, family=family).fit(
                maxiter=int(ctx.step_params.get("maxiter", 200)), disp=False
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(alpha=1.0 - confidence), dtype=np.float64)
        rows = []
        for i in range(len(terms)):
            coef = float(params[i])
            se = float(bse[i])
            z = coef / se if np.isfinite(se) and se > 0 else float("nan")
            rows.append([
                coef, se, z, float(pvalues[i]),
                float(conf[i, 0]), float(conf[i, 1]), float(np.exp(coef)),
            ])
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["row", "statistic"],
            labels={
                "row": {term: i for i, term in enumerate(terms)},
                "statistic": {
                    "coef": 0, "se": 1, "z": 2, "P": 3,
                    "CI_low": 4, "CI_high": 5, "exp_coef": 6,
                },
            },
            info={
                "method": "Inverse Gaussian GLM",
                "family": "InverseGaussian",
                "link": "log",
                "terms": terms,
                "n": int(y.size),
                "confidence": confidence,
                "aic": float(result.aic),
                "deviance": float(result.deviance),
                "null_deviance": float(result.null_deviance),
            },
        )
        self._export = {
            "terms": terms,
            "coef": params.tolist(),
            "se": bse.tolist(),
            "p": pvalues.tolist(),
            "aic": float(result.aic),
            "deviance": float(result.deviance),
            "null_deviance": float(result.null_deviance),
            "n": int(y.size),
        }
        print(f"[{self.name}] n={y.size}, terms={len(terms)}")

    def export(self, ctx: Context) -> dict:
        return self._export
