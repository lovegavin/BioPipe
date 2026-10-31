"""Left-censored normal regression (Tobit model)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._regression30_common import coefficient_rows
from ._stats21_common import design_matrix, numeric_column, table_frame


def _tobit_objective(theta, design, response, censored, censoring):
    """Negative log-likelihood and its analytic gradient."""
    beta = theta[:-1]
    log_sigma = float(theta[-1])
    sigma = float(np.exp(log_sigma))
    if not np.isfinite(sigma) or sigma <= 0:
        return np.inf, np.zeros_like(theta)
    eta = design @ beta
    z = (response - eta) / sigma
    gradient = np.zeros_like(theta)

    uncensored = ~censored
    if np.any(uncensored):
        gradient[:-1] += design[uncensored].T @ (z[uncensored] / sigma)
        gradient[-1] += float(np.sum(z[uncensored] ** 2 - 1.0))
        loglik = -0.5 * np.log(2.0 * np.pi) - log_sigma - 0.5 * z[uncensored] ** 2
        total = float(np.sum(loglik))
    else:
        total = 0.0

    if np.any(censored):
        a = (censoring - eta[censored]) / sigma
        log_cdf = norm.logcdf(a)
        log_lambda = norm.logpdf(a) - log_cdf
        lam = np.exp(np.clip(log_lambda, -745.0, 700.0))
        gradient[:-1] += -(design[censored].T @ lam) / sigma
        gradient[-1] += float(-np.sum(lam * a))
        total += float(np.sum(log_cdf))

    return -total, -gradient


def _numeric_hessian(function, point, step=1e-4):
    """Central-difference Hessian of a scalar function."""
    point = np.asarray(point, dtype=np.float64)
    size = point.size
    hessian = np.zeros((size, size), dtype=np.float64)

    def gradient(values):
        result = np.zeros(size, dtype=np.float64)
        for index in range(size):
            delta = 1e-5 * max(1.0, abs(float(values[index])))
            plus = values.copy()
            minus = values.copy()
            plus[index] += delta
            minus[index] -= delta
            result[index] = (function(plus) - function(minus)) / (2.0 * delta)
        return result

    for index in range(size):
        delta = step * max(1.0, abs(float(point[index])))
        plus = point.copy()
        minus = point.copy()
        plus[index] += delta
        minus[index] -= delta
        hessian[index] = (gradient(plus) - gradient(minus)) / (2.0 * delta)
    return (hessian + hessian.T) / 2.0


class TobitStep(Step):
    """Normal regression with left-censoring at a fixed threshold."""

    name = "tobit"
    title = "Tobit censored regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
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
            "predictors": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "categorical": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "censoring": {"type": "number", "default": 0.0},
            "max_iter": {"type": "integer", "minimum": 50, "default": 1000},
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
        censoring = float(ctx.step_params.get("censoring", 0.0))
        if not np.isfinite(censoring):
            raise StepError(f"{self.name}: censoring threshold must be finite")
        censored = response <= censoring
        if bool(censored.all()):
            raise StepError(f"{self.name}: all observations are censored")

        design, terms = design_matrix(frame, predictors, categorical, self.name)
        if response.size <= design.shape[1]:
            raise StepError(f"{self.name}: not enough observations for the model")
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: design matrix is rank deficient")

        beta0, *_ = np.linalg.lstsq(design, response, rcond=None)
        residual = response - design @ beta0
        sigma0 = float(np.std(residual, ddof=1))
        if not np.isfinite(sigma0) or sigma0 <= 0:
            sigma0 = float(np.std(response - response.mean(), ddof=1))
        if not np.isfinite(sigma0) or sigma0 <= 0:
            raise StepError(f"{self.name}: response has no positive residual scale")
        start = np.concatenate([beta0, [np.log(sigma0)]])

        def objective(theta):
            return _tobit_objective(theta, design, response, censored, censoring)

        def negative_loglik(theta):
            return objective(theta)[0]

        max_iter = int(ctx.step_params.get("max_iter", 1000))
        result = minimize(
            objective,
            start,
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": max_iter, "gtol": 1e-10, "ftol": 1e-14},
        )
        if not result.success or not np.isfinite(result.fun):
            raise StepError(f"{self.name}: fit failed: {result.message}")
        theta = np.asarray(result.x, dtype=np.float64)
        beta = theta[:-1]
        sigma = float(np.exp(theta[-1]))
        if not np.isfinite(sigma) or sigma <= 0:
            raise StepError(f"{self.name}: fitted scale is not positive")

        hessian = _numeric_hessian(negative_loglik, theta)
        try:
            covariance = np.linalg.inv(hessian)
        except np.linalg.LinAlgError as exc:
            raise StepError(f"{self.name}: Hessian is singular") from exc
        covariance = (covariance + covariance.T) / 2.0
        diagonal = np.diag(covariance)
        if not np.isfinite(diagonal).all() or np.any(diagonal <= 0):
            raise StepError(f"{self.name}: coefficient covariance is not positive")
        se = np.sqrt(diagonal)
        confidence = float(ctx.step_params.get("confidence", 0.95))
        critical = float(norm.ppf((1.0 + confidence) / 2.0))
        zvalues = beta / se[:-1]
        pvalues = 2.0 * norm.sf(np.abs(zvalues))
        interval = np.column_stack(
            [beta - critical * se[:-1], beta + critical * se[:-1]]
        )
        rows = coefficient_rows(beta, se[:-1], pvalues, interval, terms)
        block = np.asarray(rows, dtype=np.float64)
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=block,
            dims=["term", "statistic"],
            labels={
                "term": {name: index for index, name in enumerate(terms)},
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
                "method": "left-censored normal MLE",
                "n": int(response.size),
                "n_censored": int(censored.sum()),
                "censoring": censoring,
                "sigma": sigma,
                "loglik": float(-result.fun),
                "converged": bool(result.success),
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in beta],
            "se": [float(value) for value in se[:-1]],
            "z": [float(value) for value in zvalues],
            "p": [float(value) for value in pvalues],
            "sigma": sigma,
            "loglik": float(-result.fun),
            "n": int(response.size),
            "n_censored": int(censored.sum()),
            "censoring": censoring,
        }
        print(
            f"[{self.name}] n={response.size}, censored={int(censored.sum())}, "
            f"sigma={sigma:.6g}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
