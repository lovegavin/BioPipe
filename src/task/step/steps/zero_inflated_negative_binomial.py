"""Zero-inflated negative binomial regression (NB2)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class ZeroInflatedNegativeBinomialStep(Step):
    """Zero-inflated NB2 regression with logit inflation and log count links."""

    name = "zero_inflated_negative_binomial"
    title = "Zero-inflated negative binomial regression"
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
            "count_predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "zero_predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "maxiter": {"type": "integer", "minimum": 20, "default": 2000},
            "output": {"type": "string"},
        },
        "required": ["response_label", "count_predictors", "zero_predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        count_predictors = list(ctx.step_params["count_predictors"])
        zero_predictors = list(ctx.step_params["zero_predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        if not count_predictors or not zero_predictors:
            raise StepError(f"{self.name}: both predictor lists must be non-empty")
        all_predictors = list(dict.fromkeys(count_predictors + zero_predictors))
        missing = [name for name in categorical if name not in all_predictors]
        if missing:
            raise StepError(f"{self.name}: categorical names not in predictors: {missing}")
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(f"{self.name}: response {response_label!r} not found")
        for name in all_predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")

        y_raw = numeric_column(frame, response_label, self.name)
        x_design, count_terms = design_matrix(frame, count_predictors, categorical, self.name)
        z_design, zero_terms = design_matrix(frame, zero_predictors, categorical, self.name)
        keep = (
            np.isfinite(y_raw)
            & np.isfinite(x_design).all(axis=1)
            & np.isfinite(z_design).all(axis=1)
        )
        y_raw = y_raw[keep]
        x_design = x_design[keep]
        z_design = z_design[keep]
        if np.any(y_raw < 0):
            raise StepError(f"{self.name}: counts must be non-negative")
        if not np.allclose(y_raw, np.round(y_raw), atol=1e-8):
            raise StepError(f"{self.name}: counts must be integers")
        y = np.round(y_raw).astype(np.int64)
        if y.size <= x_design.shape[1] + z_design.shape[1] + 2:
            raise StepError(f"{self.name}: not enough observations")
        if np.linalg.matrix_rank(x_design) < x_design.shape[1]:
            raise StepError(f"{self.name}: count design is rank deficient")
        if np.linalg.matrix_rank(z_design) < z_design.shape[1]:
            raise StepError(f"{self.name}: zero design is rank deficient")

        try:
            result = sm.ZeroInflatedNegativeBinomialP(
                y, x_design, exog_infl=z_design, p=2
            ).fit(
                method="bfgs",
                maxiter=int(ctx.step_params.get("maxiter", 2000)),
                disp=False,
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(alpha=1.0 - confidence), dtype=np.float64)
        q = z_design.shape[1]
        p = x_design.shape[1]
        alpha = float(params[-1])
        if not np.isfinite(alpha) or alpha <= 0:
            raise StepError(f"{self.name}: fitted alpha must be positive")

        rows = []
        row_names = []
        for j, term in enumerate(count_terms):
            i = q + j
            coef = float(params[i])
            se = float(bse[i])
            zstat = coef / se if np.isfinite(se) and se > 0 else float("nan")
            rows.append([coef, se, zstat, float(pvalues[i]), float(conf[i, 0]), float(conf[i, 1]), float(np.exp(coef))])
            row_names.append(f"count:{term}")
        for j, term in enumerate(zero_terms):
            i = j
            coef = float(params[i])
            se = float(bse[i])
            zstat = coef / se if np.isfinite(se) and se > 0 else float("nan")
            rows.append([coef, se, zstat, float(pvalues[i]), float(conf[i, 0]), float(conf[i, 1]), float(np.exp(coef))])
            row_names.append(f"zero:{term}")

        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["row", "statistic"],
            labels={
                "row": {name: i for i, name in enumerate(row_names)},
                "statistic": {
                    "coef": 0, "se": 1, "z": 2, "P": 3,
                    "CI_low": 4, "CI_high": 5, "exp_coef": 6,
                },
            },
            info={
                "method": "zero-inflated negative binomial (NB2)",
                "link_count": "log",
                "link_zero": "logit",
                "count_terms": count_terms,
                "zero_terms": zero_terms,
                "n": int(y.size),
                "n_zeros": int((y == 0).sum()),
                "alpha": alpha,
                "theta": 1.0 / alpha,
                "confidence": confidence,
                "loglike": float(result.llf),
                "aic": float(result.aic),
                "bic": float(result.bic),
            },
        )
        self._export = {
            "count_terms": count_terms,
            "zero_terms": zero_terms,
            "count_coef": params[q : q + p].tolist(),
            "zero_coef": params[:q].tolist(),
            "alpha": alpha,
            "theta": 1.0 / alpha,
            "loglike": float(result.llf),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "n": int(y.size),
            "n_zeros": int((y == 0).sum()),
        }
        print(f"[{self.name}] n={y.size}, zeros={int((y == 0).sum())}, alpha={alpha:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
