"""Beta regression for response values strictly between zero and one."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class BetaRegressionStep(Step):
    """Beta regression with a logit mean link and identity precision link."""

    name = "beta_regression"
    title = "Beta regression"
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
            "max_iter": {"type": "integer", "minimum": 20, "default": 500},
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
            },
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.othermod.betareg import BetaModel

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

        y = numeric_column(frame, response_label, self.name)
        design, terms = design_matrix(frame, predictors, categorical, self.name)
        keep = np.isfinite(y) & np.isfinite(design).all(axis=1)
        y = y[keep]
        design = design[keep]
        if y.size <= design.shape[1] + 2:
            raise StepError(f"{self.name}: not enough observations")
        if np.any(y <= 0.0) or np.any(y >= 1.0):
            raise StepError(
                f"{self.name}: response must be strictly between 0 and 1"
            )
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: design matrix is rank deficient")

        max_iter = int(ctx.step_params.get("max_iter", 500))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        try:
            result = BetaModel(y, design).fit(
                disp=False, maxiter=max_iter, method="newton", cov_type="eim"
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(alpha=1.0 - confidence), dtype=np.float64)

        rows = []
        for index, _term in enumerate(terms):
            coef = float(params[index])
            se = float(bse[index])
            z = coef / se if np.isfinite(se) and se > 0 else float("nan")
            rows.append(
                [
                    coef,
                    se,
                    z,
                    float(pvalues[index]),
                    float(conf[index, 0]),
                    float(conf[index, 1]),
                ]
            )

        precision = float(np.exp(params[-1]))
        precision_se = precision * float(bse[-1])
        precision_z = float(params[-1] / bse[-1]) if bse[-1] > 0 else float("nan")
        rows.append(
            [
                precision,
                precision_se,
                precision_z,
                float(pvalues[-1]),
                float(np.exp(conf[-1, 0])),
                float(np.exp(conf[-1, 1])),
            ]
        )
        labels = list(terms) + ["phi"]

        block = np.asarray(rows, dtype=np.float64)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["row", "statistic"],
            labels={
                "row": {label: index for index, label in enumerate(labels)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                },
            },
            info={
                "method": "Beta regression",
                "mean_link": "logit",
                "precision_link": "identity",
                "terms": labels,
                "n": int(y.size),
                "llf": float(result.llf),
                "aic": float(result.aic),
                "bic": float(result.bic),
            },
        )
        self._export = {
            "terms": labels,
            "coef": params[:-1].tolist() + [precision],
            "se": bse[:-1].tolist() + [precision_se],
            "p": pvalues.tolist(),
            "llf": float(result.llf),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "n": int(y.size),
        }
        print(f"[{self.name}] n={y.size}, terms={len(labels)}")

    def export(self, ctx: Context) -> dict:
        return self._export
