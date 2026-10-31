"""Weibull accelerated failure-time regression for interval-censored data."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


_STATISTICS = ["coef", "se", "z", "P", "CI_low", "CI_high"]


def _design(frame, covariates: list[str], step_name: str) -> np.ndarray:
    columns = [np.ones(len(frame), dtype=np.float64)]
    for name in covariates:
        columns.append(numeric_column(frame, name, step_name))
    return np.column_stack(columns)


def _log_survival(
    time: np.ndarray, linear: np.ndarray, sigma: float
) -> np.ndarray:
    """log S(t) for a Weibull AFT with log-time location ``linear``."""
    values = np.full(time.shape, -np.inf, dtype=np.float64)
    positive = time > 0
    if positive.any():
        z = (np.log(time[positive]) - linear[positive]) / sigma
        z = np.clip(z, -700.0, 700.0)
        values[positive] = -np.exp(z)
    return values


def _log_interval(
    lower: np.ndarray,
    upper: np.ndarray,
    linear: np.ndarray,
    sigma: float,
) -> np.ndarray:
    """log P(lower < T <= upper), with 0 and inf as open bounds."""
    log_survival_lower = _log_survival(lower, linear, sigma)
    finite_upper = np.isfinite(upper)
    log_survival_upper = np.full(lower.shape, -np.inf, dtype=np.float64)
    if finite_upper.any():
        log_survival_upper[finite_upper] = _log_survival(
            upper[finite_upper], linear[finite_upper], sigma
        )

    result = np.full(lower.shape, -np.inf, dtype=np.float64)
    left = lower <= 0
    if left.any():
        # 1 - S(upper) = -expm1(log S(upper)).
        result[left] = np.log(-np.expm1(log_survival_upper[left]))
    interior = ~left & finite_upper
    if interior.any():
        a = log_survival_lower[interior]
        b = log_survival_upper[interior]
        # log(S(lower) - S(upper)) = a + log(1 - exp(b-a)).
        delta = b - a
        with np.errstate(divide="ignore", invalid="ignore"):
            result[interior] = a + np.log(-np.expm1(delta))
    right = ~finite_upper
    result[right] = log_survival_lower[right]
    return result


def _exact_log_density(
    time: np.ndarray, linear: np.ndarray, sigma: float
) -> np.ndarray:
    z = (np.log(time) - linear) / sigma
    z = np.clip(z, -700.0, 700.0)
    with np.errstate(over="ignore", under="ignore"):
        return -np.log(sigma) - np.log(time) + z - np.exp(z)


class IntervalCensoredRegressionStep(Step):
    """Fit a Weibull AFT model to interval-censored observations.

    Each row supplies a lower and upper observation time.  ``lower < upper``
    is an interval, ``lower == upper`` is exact, ``upper = inf`` is right
    censored, and ``lower <= 0`` is left censored.  The likelihood is the
    interval probability under a Weibull AFT model, the same model fitted by
    R's ``survival::survreg(..., dist="weibull")`` for interval2 responses.
    """

    name = "interval_censored_regression"
    title = "Interval-censored Weibull AFT"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = [
        "numpy>=1.24",
        "scipy>=1.10",
    ]
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
            "time_lower_label": {
                "type": "string",
                "title": "区间下界列",
            },
            "time_upper_label": {
                "type": "string",
                "title": "区间上界列",
            },
            "covariates": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "uniqueItems": True,
                "title": "自变量列",
            },
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
                "title": "置信水平",
            },
            "max_iter": {
                "type": "integer",
                "minimum": 50,
                "maximum": 2000,
                "default": 500,
                "title": "最大迭代次数",
            },
            "output": {"type": "string"},
        },
        "required": [
            "time_lower_label",
            "time_upper_label",
            "covariates",
        ],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        lower_label = ctx.step_params["time_lower_label"]
        upper_label = ctx.step_params["time_upper_label"]
        covariates = list(ctx.step_params["covariates"])
        confidence = float(ctx.step_params.get("confidence", 0.95))
        max_iter = int(ctx.step_params.get("max_iter", 500))
        out_name = ctx.step_params.get("output", self.name)

        if not covariates:
            raise StepError(f"{self.name}: need at least one covariate")
        if len(covariates) != len(set(covariates)):
            raise StepError(f"{self.name}: covariates must be unique")
        if lower_label == upper_label:
            raise StepError(
                f"{self.name}: lower and upper time labels must differ"
            )
        if lower_label in covariates or upper_label in covariates:
            raise StepError(
                f"{self.name}: time labels must not also be covariates"
            )
        if not 0.0 < confidence < 1.0:
            raise StepError(f"{self.name}: confidence must be in (0, 1)")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        lower_raw = numeric_column(frame, lower_label, self.name)
        upper_raw = numeric_column(frame, upper_label, self.name)
        design = _design(frame, covariates, self.name)
        keep = np.isfinite(lower_raw) & ~np.isnan(upper_raw)
        for index in range(1, design.shape[1]):
            keep &= np.isfinite(design[:, index])
        lower = np.asarray(lower_raw[keep], dtype=np.float64)
        upper = np.asarray(upper_raw[keep], dtype=np.float64)
        design = design[keep]
        samples = (
            frame.loc[keep, "__sample__"].astype(str).to_numpy().tolist()
        )
        n = int(lower.size)
        if n < 10:
            raise StepError(f"{self.name}: need at least 10 complete rows")
        if np.any(lower < 0):
            raise StepError(f"{self.name}: lower times must be nonnegative")
        if np.any(upper < lower):
            raise StepError(
                f"{self.name}: upper times must be greater than or equal to lower times"
            )
        if np.any(np.isneginf(upper)):
            raise StepError(f"{self.name}: upper times must not be -inf")
        if not np.isfinite(upper).any():
            raise StepError(
                f"{self.name}: at least one finite upper time is required"
            )
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: covariate design is rank deficient")

        exact = np.isfinite(upper) & (upper == lower)
        finite = np.isfinite(upper)
        left_censored = finite & (lower <= 0)
        proper_interval = finite & ~exact & ~left_censored
        if not np.any(finite & ~exact) and np.all(exact):
            raise StepError(
                f"{self.name}: exact-only data are not interval censored"
            )

        midpoint = np.where(finite, (lower + upper) / 2.0, lower + 1.0)
        midpoint = np.maximum(midpoint, 1e-12)
        log_midpoint = np.log(midpoint)
        try:
            initial_beta, *_ = np.linalg.lstsq(
                design, log_midpoint, rcond=None
            )
        except np.linalg.LinAlgError as exc:
            raise StepError(
                f"{self.name}: could not initialize regression: {exc}"
            ) from exc
        residual = log_midpoint - design @ initial_beta
        initial_sigma = float(np.std(residual, ddof=1))
        if not np.isfinite(initial_sigma) or initial_sigma <= 0:
            initial_sigma = 1.0
        theta0 = np.concatenate(
            [np.asarray(initial_beta, dtype=np.float64), [np.log(initial_sigma)]]
        )

        def negative_loglik(theta: np.ndarray) -> float:
            beta = theta[:-1]
            log_sigma = float(theta[-1])
            if not np.isfinite(log_sigma) or not -8.0 < log_sigma < 8.0:
                return 1e300
            sigma = float(np.exp(log_sigma))
            if not np.isfinite(sigma) or sigma <= 0:
                return 1e300
            linear = design @ beta
            loglik = np.zeros(n, dtype=np.float64)
            if exact.any():
                loglik[exact] = _exact_log_density(
                    lower[exact], linear[exact], sigma
                )
            interval = finite & ~exact
            if interval.any():
                loglik[interval] = _log_interval(
                    lower[interval],
                    upper[interval],
                    linear[interval],
                    sigma,
                )
            right = ~finite
            if right.any():
                loglik[right] = _log_survival(
                    lower[right], linear[right], sigma
                )
            if not np.isfinite(loglik).all():
                return 1e300
            value = -float(np.sum(loglik))
            return value if np.isfinite(value) else 1e300

        bounds = [(None, None)] * design.shape[1] + [(-8.0, 8.0)]
        try:
            fitted = minimize(
                negative_loglik,
                theta0,
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": max_iter, "ftol": 1e-12},
            )
        except (ValueError, FloatingPointError) as exc:
            raise StepError(
                f"{self.name}: interval-censored fit failed: {exc}"
            ) from exc
        if not fitted.success:
            raise StepError(
                f"{self.name}: interval-censored fit did not converge: "
                f"{fitted.message}"
            )
        theta = np.asarray(fitted.x, dtype=np.float64)
        log_sigma = float(theta[-1])
        sigma = float(np.exp(log_sigma))
        if not np.isfinite(theta).all() or not np.isfinite(negative_loglik(theta)):
            raise StepError(f"{self.name}: fitted parameters are not finite")

        def gradient(point: np.ndarray) -> np.ndarray:
            step = 1e-5 * (1.0 + np.abs(point))
            out = np.empty_like(point)
            for index in range(point.size):
                plus = point.copy()
                minus = point.copy()
                plus[index] += step[index]
                minus[index] -= step[index]
                out[index] = (
                    negative_loglik(plus) - negative_loglik(minus)
                ) / (2.0 * step[index])
            return out

        try:
            hessian = np.empty((theta.size, theta.size), dtype=np.float64)
            step = 1e-4 * (1.0 + np.abs(theta))
            for row in range(theta.size):
                plus = theta.copy()
                minus = theta.copy()
                plus[row] += step[row]
                minus[row] -= step[row]
                hessian[row] = (gradient(plus) - gradient(minus)) / (
                    2.0 * step[row]
                )
            hessian = 0.5 * (hessian + hessian.T)
            covariance = np.linalg.inv(hessian)
        except np.linalg.LinAlgError as exc:
            raise StepError(
                f"{self.name}: observed information is singular: {exc}"
            ) from exc
        if not np.isfinite(covariance).all():
            raise StepError(f"{self.name}: covariance is not finite")
        standard_errors = np.sqrt(np.diag(covariance))
        if not np.isfinite(standard_errors).all() or np.any(standard_errors <= 0):
            raise StepError(f"{self.name}: standard errors are invalid")

        z_values = theta / standard_errors
        p_values = 2.0 * norm.sf(np.abs(z_values))
        critical = float(norm.ppf(0.5 + confidence / 2.0))
        ci_low = theta - critical * standard_errors
        ci_high = theta + critical * standard_errors

        terms = ["Intercept", *covariates, "log_scale"]
        values = np.column_stack(
            [theta, standard_errors, z_values, p_values, ci_low, ci_high]
        ).astype(np.float64)
        if not np.isfinite(values).all():
            raise StepError(f"{self.name}: coefficient table is not finite")

        loglik = -negative_loglik(theta)
        ctx[out_name] = Form(
            data=values,
            dims=["term", "statistic"],
            labels={
                "term": {name: index for index, name in enumerate(terms)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "method": "interval_censored_weibull_aft",
                "distribution": "weibull",
                "parameterization": "log_time_location_scale",
                "confidence": confidence,
                "n": n,
                "n_covariates": len(covariates),
                "n_exact": int(exact.sum()),
                "n_interval": int(proper_interval.sum()),
                "n_right": int((~finite).sum()),
                "n_left": int(left_censored.sum()),
                "loglik": float(loglik),
                "scale": sigma,
                "shape": 1.0 / sigma,
                "converged": bool(fitted.success),
                "iterations": int(fitted.nit),
            },
        )
        self._export = {
            "samples": samples,
            "lower": lower.tolist(),
            "upper": upper.tolist(),
            "terms": terms,
            "coefficients": theta.tolist(),
            "standard_errors": standard_errors.tolist(),
            "z": z_values.tolist(),
            "p": p_values.tolist(),
            "ci_low": ci_low.tolist(),
            "ci_high": ci_high.tolist(),
            "log_scale": log_sigma,
            "scale": sigma,
            "shape": 1.0 / sigma,
            "loglik": float(loglik),
            "n": n,
            "n_exact": int(exact.sum()),
            "n_interval": int(proper_interval.sum()),
            "n_right": int((~finite).sum()),
            "n_left": int(left_censored.sum()),
            "confidence": confidence,
            "converged": bool(fitted.success),
            "iterations": int(fitted.nit),
        }
        print(
            f"[{self.name}] n={n}, scale={sigma:.4f}, "
            f"loglik={loglik:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
