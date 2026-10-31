"""Fine-Gray subdistribution hazard regression.

The implementation follows the weighted partial-likelihood form of
Fine and Gray (1999).  At each event time the risk set contains
subjects still under observation plus subjects that already failed
from a competing cause; the latter receive the time-dependent weight
``G(t) / G(T_i)`` where ``G`` is the Kaplan-Meier estimate of the
censoring distribution.  Covariates are used without an intercept.

Output form
-----------
    dims    = ["term", "statistic"]
    labels  = {term: {name: i},
               statistic: {"coef": 0, "HR": 1, "se": 2,
                           "z": 3, "P": 4,
                           "CI_low": 5, "CI_high": 6}}

The reported standard errors use the robust sandwich estimator, matching
``cmprsk::crr`` (the ``var`` component), rather than the naive inverse
information.

Params:
    time_label   : follow-up time column (required)
    event_label  : event-code column (required)
    covariates   : non-empty list of numeric covariate columns
    event_code   : code for the event of interest (default 1)
    censor_code  : code for administrative censoring (default 0)
    confidence   : confidence level for coefficient intervals (default .95)
    max_iter     : maximum Newton iterations (default 100)
    output       : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


_STAT_LABELS = {
    "coef": 0,
    "HR": 1,
    "se": 2,
    "z": 3,
    "P": 4,
    "CI_low": 5,
    "CI_high": 6,
}


def _censor_survival(time: np.ndarray, censor: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kaplan-Meier survival for the censoring indicator."""
    order = np.argsort(time, kind="mergesort")
    ordered_time = time[order]
    ordered_censor = censor[order]
    n = ordered_time.size
    survival = 1.0
    seen: dict[float, float] = {}
    i = 0
    while i < n:
        j = i
        while j < n and ordered_time[j] == ordered_time[i]:
            j += 1
        at_risk = n - i
        censored = int(ordered_censor[i:j].sum())
        if censored:
            survival *= 1.0 - censored / at_risk
        for k in range(i, j):
            seen[float(ordered_time[k])] = survival
        i = j
    keys = np.asarray(sorted(seen), dtype=np.float64)
    values = np.asarray([seen[key] for key in keys], dtype=np.float64)
    return keys, values


def _fit_fine_gray(
    time: np.ndarray,
    status: np.ndarray,
    covariates: np.ndarray,
    event_code: int,
    censor_code: int,
    max_iter: int,
):
    """Fit the weighted Fine-Gray partial likelihood.

    Returns ``(beta, covariance, loglik, iterations, n_events,
    n_competing, n_censored)``.  Covariance is the robust sandwich
    estimator used by ``cmprsk::crr``.
    """
    n, k = covariates.shape
    event = status == event_code
    censor = status == censor_code
    competing = ~(event | censor)
    event_times = np.unique(time[event])
    censor_times, censor_values = _censor_survival(time, censor.astype(np.float64))
    weight_cache: dict[float, float] = {}

    def censor_survival_at(value: float) -> float:
        if value not in weight_cache:
            position = int(np.searchsorted(censor_times, value, side="right")) - 1
            weight_cache[value] = 1.0 if position < 0 else float(censor_values[position])
        return weight_cache[value]

    def evaluate(beta: np.ndarray, need_hessian: bool):
        eta = covariates @ beta
        loglik = 0.0
        gradient = np.zeros(k, dtype=np.float64)
        hessian = np.zeros((k, k), dtype=np.float64)
        for event_time in event_times:
            event_rows = np.flatnonzero(event & (time == event_time))
            d = int(event_rows.size)
            risk_mask = (time >= event_time) | ((time < event_time) & competing)
            risk_rows = np.flatnonzero(risk_mask)
            weights = np.ones(risk_rows.size, dtype=np.float64)
            prior_competing = (time[risk_rows] < event_time) & competing[risk_rows]
            if np.any(prior_competing):
                numerator = censor_survival_at(float(event_time))
                for position in np.flatnonzero(prior_competing):
                    denominator = censor_survival_at(float(time[risk_rows[position]]))
                    weights[position] = numerator / denominator if denominator > 0.0 else 0.0
            weighted = weights * np.exp(eta[risk_rows])
            total = float(weighted.sum())
            if not np.isfinite(total) or total <= 0.0:
                raise StepError("fine_gray: invalid risk-set weight; check time/covariates")
            mean = (weighted[:, None] * covariates[risk_rows]).sum(axis=0) / total
            loglik += float(eta[event_rows].sum()) - d * float(np.log(total))
            gradient += covariates[event_rows].sum(axis=0) - d * mean
            if need_hessian:
                centered = weighted[:, None] * covariates[risk_rows]
                second = centered.T @ covariates[risk_rows] / total
                hessian += -d * (second - np.outer(mean, mean))
        return loglik, gradient, hessian

    beta = np.zeros(k, dtype=np.float64)
    converged = False
    iterations = 0
    for iteration in range(1, max_iter + 1):
        iterations = iteration
        loglik, gradient, hessian = evaluate(beta, True)
        try:
            step = np.linalg.solve(-hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(-hessian, gradient, rcond=None)[0]
        if not np.all(np.isfinite(step)):
            raise StepError("fine_gray: Newton step is not finite")
        scale = 1.0
        while scale > 1e-12:
            candidate = beta + scale * step
            candidate_loglik, _, _ = evaluate(candidate, False)
            if candidate_loglik >= loglik + 1e-4 * scale * float(np.dot(gradient, step)):
                break
            scale *= 0.5
        beta = beta + scale * step
        if float(np.max(np.abs(scale * step))) < 1e-9:
            converged = True
            break
    if not converged:
        raise StepError(f"fine_gray: Newton did not converge after {max_iter} iterations")

    loglik, gradient, hessian = evaluate(beta, True)
    information = -hessian
    try:
        inverse_information = np.linalg.inv(information)
    except np.linalg.LinAlgError as exc:
        raise StepError("fine_gray: information matrix is singular") from exc

    # Robust sandwich: sum of per-subject efficient score contributions.
    scores = np.zeros((n, k), dtype=np.float64)
    eta = covariates @ beta
    for event_time in event_times:
        event_rows = np.flatnonzero(event & (time == event_time))
        d = int(event_rows.size)
        risk_mask = (time >= event_time) | ((time < event_time) & competing)
        risk_rows = np.flatnonzero(risk_mask)
        weights = np.ones(risk_rows.size, dtype=np.float64)
        prior_competing = (time[risk_rows] < event_time) & competing[risk_rows]
        if np.any(prior_competing):
            numerator = censor_survival_at(float(event_time))
            for position in np.flatnonzero(prior_competing):
                denominator = censor_survival_at(float(time[risk_rows[position]]))
                weights[position] = numerator / denominator if denominator > 0.0 else 0.0
        weighted = weights * np.exp(eta[risk_rows])
        total = float(weighted.sum())
        mean = (weighted[:, None] * covariates[risk_rows]).sum(axis=0) / total
        scores[risk_rows] += (
            -d * weighted[:, None] / total * (covariates[risk_rows] - mean)
        )
        scores[event_rows] += covariates[event_rows] - mean
    meat = scores.T @ scores
    covariance = inverse_information @ meat @ inverse_information
    return (
        beta,
        covariance,
        loglik,
        iterations,
        int(event.sum()),
        int(competing.sum()),
        int(censor.sum()),
    )


class FineGrayStep(Step):
    """Fine-Gray subdistribution hazard regression."""

    name = "fine_gray"
    title = "Fine-Gray subdistribution regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "pandas>=2.0", "scipy>=1.10"]
    dependency_imports = ["numpy", "pandas", "scipy"]
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
            "time_label": {"type": "string", "title": "随访时间列"},
            "event_label": {"type": "string", "title": "结局代码列"},
            "covariates": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "title": "协变量列",
            },
            "event_code": {"type": "integer", "default": 1, "title": "目标事件代码"},
            "censor_code": {"type": "integer", "default": 0, "title": "删失代码"},
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
            },
            "max_iter": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
            "output": {"type": "string"},
        },
        "required": ["time_label", "event_label", "covariates"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        time_label = ctx.step_params["time_label"]
        event_label = ctx.step_params["event_label"]
        covariates = list(ctx.step_params["covariates"])
        event_code = int(ctx.step_params.get("event_code", 1))
        censor_code = int(ctx.step_params.get("censor_code", 0))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        max_iter = int(ctx.step_params.get("max_iter", 100))
        out_name = ctx.step_params.get("output", self.name)

        if not covariates:
            raise StepError(f"{self.name}: 'covariates' must be a non-empty list")
        if event_code == censor_code:
            raise StepError(f"{self.name}: event_code and censor_code must differ")
        if not 0.0 < confidence < 1.0:
            raise StepError(f"{self.name}: confidence must be in (0, 1)")

        frame = table_frame(form, sample_dim, feature_dim, self.name)
        time = numeric_column(frame, time_label, self.name)
        status_raw = numeric_column(frame, event_label, self.name)
        matrix = np.column_stack([numeric_column(frame, name, self.name) for name in covariates])
        keep = np.isfinite(time) & np.isfinite(status_raw) & np.all(np.isfinite(matrix), axis=1)
        time = time[keep]
        status_raw = status_raw[keep]
        matrix = matrix[keep]
        if time.size < max(5, matrix.shape[1] + 2):
            raise StepError(f"{self.name}: too few complete observations")
        if np.any(time <= 0.0):
            raise StepError(f"{self.name}: follow-up times must be positive")
        rounded = np.rint(status_raw)
        if not np.allclose(status_raw, rounded, atol=1e-9):
            raise StepError(f"{self.name}: event codes must be integers")
        status = rounded.astype(np.int64)
        event = status == event_code
        if int(event.sum()) < 2:
            raise StepError(f"{self.name}: at least two target events are required")
        if np.linalg.matrix_rank(matrix) < matrix.shape[1]:
            raise StepError(f"{self.name}: covariate matrix is rank deficient")

        beta, covariance, loglik, iterations, n_events, n_competing, n_censored = _fit_fine_gray(
            time, status, matrix, event_code, censor_code, max_iter
        )
        se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
        if np.any(se <= 0.0) or not np.all(np.isfinite(se)):
            raise StepError(f"{self.name}: non-positive standard error; model may be ill-conditioned")
        z_values = beta / se
        p_values = 2.0 * norm.sf(np.abs(z_values))
        critical = float(norm.ppf(0.5 + confidence / 2.0))

        data = np.zeros((len(covariates), len(_STAT_LABELS)), dtype=np.float64)
        per_row = []
        for index, name in enumerate(covariates):
            coef = float(beta[index])
            standard_error = float(se[index])
            row = {
                "term": name,
                "coef": coef,
                "HR": float(np.exp(coef)),
                "se": standard_error,
                "z": float(z_values[index]),
                "P": float(p_values[index]),
                "CI_low": float(coef - critical * standard_error),
                "CI_high": float(coef + critical * standard_error),
            }
            data[index] = [row[key] for key in _STAT_LABELS]
            per_row.append(row)

        ctx[out_name] = Form(
            data=data,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(covariates)},
                "statistic": dict(_STAT_LABELS),
            },
            info={
                "missing_code": np.nan,
                "method": "fine_gray",
                "variance": "robust",
                "n": int(time.size),
                "n_events": n_events,
                "n_competing": n_competing,
                "n_censored": n_censored,
                "n_covariates": len(covariates),
                "loglik": float(loglik),
                "iterations": int(iterations),
                "converged": True,
                "event_code": event_code,
                "censor_code": censor_code,
                "confidence": confidence,
            },
        )
        self._export_data = {
            "method": "fine_gray",
            "variance": "robust",
            "time_label": time_label,
            "event_label": event_label,
            "covariates": list(covariates),
            "event_code": event_code,
            "censor_code": censor_code,
            "n": int(time.size),
            "n_events": n_events,
            "n_competing": n_competing,
            "n_censored": n_censored,
            "loglik": float(loglik),
            "iterations": int(iterations),
            "results": per_row,
        }
        print(
            f"[{self.name}] {len(covariates)} covariates, n={time.size}, "
            f"events={n_events}, competing={n_competing}, loglik={loglik:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
