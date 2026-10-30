"""Zero-inflated Poisson regression."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class ZeroInflatedPoissonStep(Step):
    """Poisson count model with a logistic zero-inflation component."""

    name = "zero_inflated_poisson"
    title = "Zero-inflated Poisson regression"
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
            "count_predictors": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "zero_predictors": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["response_label", "count_predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.discrete.count_model import ZeroInflatedPoisson

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        count_predictors = list(ctx.step_params["count_predictors"])
        zero_predictors = list(ctx.step_params.get("zero_predictors", []))
        categorical = list(ctx.step_params.get("categorical", []))
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(f"{self.name}: response {response_label!r} not found")
        for name in count_predictors + zero_predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")
        missing = [name for name in categorical if name not in count_predictors]
        if missing:
            raise StepError(
                f"{self.name}: categorical names not in count_predictors: {missing}"
            )

        y = numeric_column(frame, response_label, self.name)
        count_design, count_terms = design_matrix(
            frame, count_predictors, categorical, self.name
        )
        if zero_predictors:
            zero_design, zero_terms = design_matrix(
                frame, zero_predictors, [], self.name
            )
        else:
            zero_design = np.ones((len(frame), 1), dtype=np.float64)
            zero_terms = ["Intercept"]
        keep = (
            np.isfinite(y)
            & np.isfinite(count_design).all(axis=1)
            & np.isfinite(zero_design).all(axis=1)
        )
        y = y[keep]
        count_design = count_design[keep]
        zero_design = zero_design[keep]
        if np.any(y < 0) or np.any(np.abs(y - np.round(y)) > 1e-8):
            raise StepError(f"{self.name}: response must contain non-negative counts")
        if y.size <= count_design.shape[1] + zero_design.shape[1] + 2:
            raise StepError(f"{self.name}: not enough observations")
        if np.linalg.matrix_rank(count_design) < count_design.shape[1]:
            raise StepError(f"{self.name}: count design matrix is rank deficient")
        if np.linalg.matrix_rank(zero_design) < zero_design.shape[1]:
            raise StepError(f"{self.name}: zero design matrix is rank deficient")

        maxiter = int(ctx.step_params.get("maxiter", 200))
        try:
            result = ZeroInflatedPoisson(
                np.asarray(y, dtype=np.int64),
                count_design,
                exog_infl=zero_design,
            ).fit(disp=False, maxiter=maxiter)
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        n_zero = len(zero_terms)
        rows = []
        labels = []
        for i, term in enumerate(zero_terms):
            coef = float(params[i])
            se = float(bse[i])
            rows.append(
                [
                    coef,
                    se,
                    coef / se if np.isfinite(se) and se > 0 else float("nan"),
                    float(pvalues[i]),
                    float(conf[i, 0]),
                    float(conf[i, 1]),
                    float(np.exp(coef)),
                ]
            )
            labels.append(f"zero|{term}")
        for j, term in enumerate(count_terms):
            i = n_zero + j
            coef = float(params[i])
            se = float(bse[i])
            rows.append(
                [
                    coef,
                    se,
                    coef / se if np.isfinite(se) and se > 0 else float("nan"),
                    float(pvalues[i]),
                    float(conf[i, 0]),
                    float(conf[i, 1]),
                    float(np.exp(coef)),
                ]
            )
            labels.append(f"count|{term}")

        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["row", "statistic"],
            labels={
                "row": {label: i for i, label in enumerate(labels)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "exp_coef": 6,
                },
            },
            info={
                "method": "zero-inflated Poisson",
                "count_terms": count_terms,
                "zero_terms": zero_terms,
                "n": int(y.size),
                "llf": float(result.llf),
                "aic": float(result.aic),
            },
        )
        self._export = {
            "count_terms": count_terms,
            "zero_terms": zero_terms,
            "count_coef": params[n_zero:].tolist(),
            "zero_coef": params[:n_zero].tolist(),
            "llf": float(result.llf),
            "aic": float(result.aic),
            "n": int(y.size),
        }
        print(f"[{self.name}] n={y.size}, count_terms={len(count_terms)}, zero_terms={n_zero}")

    def export(self, ctx: Context) -> dict:
        return self._export
