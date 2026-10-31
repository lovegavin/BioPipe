"""Conditional logistic regression for matched case-control data.

The conditional likelihood removes one intercept per stratum, so only
within-stratum contrasts of the covariates are used.  The implementation
uses Newton-Raphson on the exact conditional likelihood and the observed
information for standard errors.

Output form
-----------
    dims    = ["term", "statistic"]
    labels  = {term: {covariate: i},
               statistic: {"coef": 0, "se": 1, "z": 2, "P": 3,
                           "CI_low": 4, "CI_high": 5, "OR": 6}}

Params:
    stratum_label : column identifying matched sets (required)
    outcome_label : binary case/control column (required)
    covariates    : non-empty list of numeric covariate columns
    confidence    : confidence level for coefficient intervals (default .95)
    max_iter      : maximum Newton iterations (default 100)
    tol           : convergence tolerance on the Newton step (default 1e-8)
    output        : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


_STATISTICS = ["coef", "se", "z", "P", "CI_low", "CI_high", "OR"]


def _fit_conditional_logistic(
    x: np.ndarray,
    y: np.ndarray,
    strata: np.ndarray,
    max_iter: int,
    tol: float,
):
    """Return ``(beta, covariance, loglik, iterations)``.

    ``strata`` is an integer vector; every stratum must contain at least
    one case and one control.  The conditional likelihood is

        sum_i y_i x_i' beta - sum_s log(sum_{j in s} exp(x_j' beta)).

    There is deliberately no intercept: it cancels within each stratum.
    """

    k = x.shape[1]
    groups = [np.flatnonzero(strata == value) for value in np.unique(strata)]
    beta = np.zeros(k, dtype=np.float64)
    loglik = -np.inf

    def evaluate(current: np.ndarray, need_hessian: bool):
        linear = x @ current
        total = 0.0
        gradient = np.zeros(k, dtype=np.float64)
        hessian = np.zeros((k, k), dtype=np.float64)
        for rows in groups:
            values = linear[rows]
            offset = float(values.max())
            weights = np.exp(values - offset)
            weights /= weights.sum()
            cases = y[rows] == 1
            total += float(values[cases].sum()) - (
                offset + float(np.log(np.exp(values - offset).sum()))
            )
            weighted_x = weights @ x[rows]
            gradient += x[rows][cases].sum(axis=0) - weighted_x
            if need_hessian:
                xs = x[rows]
                hessian -= (xs.T * weights) @ xs - np.outer(
                    weighted_x, weighted_x
                )
        return total, gradient, hessian

    converged = False
    for iteration in range(1, max_iter + 1):
        loglik, gradient, hessian = evaluate(beta, True)
        if not (
            np.isfinite(loglik)
            and np.isfinite(gradient).all()
            and np.isfinite(hessian).all()
        ):
            raise StepError("conditional_logistic: non-finite likelihood")
        try:
            step = np.linalg.solve(-hessian, gradient)
        except np.linalg.LinAlgError as exc:
            raise StepError(
                "conditional_logistic: information matrix is singular"
            ) from exc
        if not np.isfinite(step).all():
            raise StepError("conditional_logistic: non-finite Newton step")

        scale = 1.0
        accepted = False
        for _ in range(24):
            candidate = beta + scale * step
            trial, _, _ = evaluate(candidate, False)
            if np.isfinite(trial) and trial >= loglik - 1e-12:
                beta = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            raise StepError(
                "conditional_logistic: line search failed to improve likelihood"
            )
        if float(np.max(np.abs(scale * step))) <= tol:
            converged = True
            break

    if not converged:
        raise StepError(
            f"conditional_logistic: Newton iterations did not converge "
            f"within {max_iter}"
        )

    loglik, gradient, hessian = evaluate(beta, True)
    if not np.isfinite(loglik) or not np.isfinite(hessian).all():
        raise StepError("conditional_logistic: non-finite final likelihood")
    try:
        covariance = np.linalg.inv(-hessian)
    except np.linalg.LinAlgError as exc:
        raise StepError(
            "conditional_logistic: final information matrix is singular"
        ) from exc
    if not np.isfinite(covariance).all():
        raise StepError("conditional_logistic: non-finite covariance")
    return beta, covariance, float(loglik), iteration


class ConditionalLogisticStep(Step):
    """Fit a conditional logistic model for matched case-control strata."""

    name = "conditional_logistic"
    title = "Conditional logistic regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy", "scipy", "pandas"]
    dependency_imports = ["numpy", "scipy", "pandas"]
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
            "stratum_label": {"type": "string"},
            "outcome_label": {"type": "string"},
            "covariates": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "uniqueItems": True,
            },
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
            },
            "max_iter": {"type": "integer", "minimum": 10, "default": 100},
            "tol": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 0.001,
                "default": 1e-8,
            },
            "output": {"type": "string"},
        },
        "required": ["stratum_label", "outcome_label", "covariates"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        stratum_label = ctx.step_params["stratum_label"]
        outcome_label = ctx.step_params["outcome_label"]
        covariates = list(ctx.step_params["covariates"])
        confidence = float(ctx.step_params.get("confidence", 0.95))
        max_iter = int(ctx.step_params.get("max_iter", 100))
        tol = float(ctx.step_params.get("tol", 1e-8))
        out_name = ctx.step_params.get("output", self.name)

        if outcome_label in covariates:
            raise StepError(
                f"{self.name}: outcome {outcome_label!r} cannot be a covariate"
            )
        if stratum_label in covariates:
            raise StepError(
                f"{self.name}: stratum {stratum_label!r} cannot be a covariate"
            )

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        for name in (stratum_label, outcome_label, *covariates):
            if name not in frame.columns:
                raise StepError(f"{self.name}: column {name!r} not found")

        valid = frame[stratum_label].notna() & frame[outcome_label].notna()
        for name in covariates:
            valid &= np.isfinite(
                pd.to_numeric(frame[name], errors="coerce")
            )
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 4:
            raise StepError(f"{self.name}: fewer than four complete rows")

        raw_outcome = pd.to_numeric(frame[outcome_label], errors="coerce")
        if not raw_outcome.notna().all():
            raise StepError(f"{self.name}: outcome must be numeric")
        outcome_values = np.asarray(raw_outcome, dtype=np.float64)
        levels = sorted(set(outcome_values.tolist()))
        if len(levels) != 2:
            raise StepError(
                f"{self.name}: outcome must have exactly two levels"
            )
        if levels == [0.0, 1.0]:
            y = outcome_values.astype(np.int64)
            level_labels = ["0", "1"]
        else:
            low, high = levels
            y = (outcome_values == high).astype(np.int64)
            level_labels = [str(low), str(high)]

        strata_raw = frame[stratum_label].astype(str).to_numpy()
        strata_codes, strata_values = pd.factorize(strata_raw, sort=True)
        strata = np.asarray(strata_codes, dtype=np.int64)
        n_strata = len(strata_values)
        if n_strata < 2:
            raise StepError(f"{self.name}: at least two strata are required")

        for code in range(n_strata):
            mask = strata == code
            if not np.any(y[mask] == 1):
                raise StepError(
                    f"{self.name}: stratum {strata_values[code]!r} has no case"
                )
            if not np.any(y[mask] == 0):
                raise StepError(
                    f"{self.name}: stratum {strata_values[code]!r} has no control"
                )

        columns = []
        for name in covariates:
            values = numeric_column(frame, name, self.name)
            if not np.isfinite(values).all():
                raise StepError(
                    f"{self.name}: covariate {name!r} has non-finite values"
                )
            columns.append(values)
        x = np.column_stack(columns)
        if x.shape[1] == 0:
            raise StepError(f"{self.name}: no covariates remain")
        if x.shape[1] >= x.shape[0]:
            raise StepError(f"{self.name}: too many covariates for the rows")

        # A covariate that is constant within every stratum is absorbed by
        # the stratum intercept and cannot be identified.
        centered = x.copy()
        for code in range(n_strata):
            mask = strata == code
            centered[mask] -= centered[mask].mean(axis=0)
        if np.linalg.matrix_rank(centered) < x.shape[1]:
            raise StepError(
                f"{self.name}: covariates are collinear within strata"
            )

        beta, covariance, loglik, iterations = _fit_conditional_logistic(
            x, y, strata, max_iter, tol
        )
        se = np.sqrt(np.diag(covariance))
        if not np.isfinite(se).all() or np.any(se <= 0):
            raise StepError(f"{self.name}: fitted standard errors are invalid")
        zvalues = beta / se
        pvalues = 2.0 * norm.sf(np.abs(zvalues))
        critical = float(norm.ppf(0.5 + confidence / 2.0))
        ci_low = beta - critical * se
        ci_high = beta + critical * se
        odds_ratios = np.exp(beta)

        table = np.column_stack(
            [beta, se, zvalues, pvalues, ci_low, ci_high, odds_ratios]
        )
        ctx[out_name] = Form(
            data=table,
            dims=["term", "statistic"],
            labels={
                "term": {name: index for index, name in enumerate(covariates)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "method": "conditional_logistic",
                "link": "logit",
                "n": int(len(y)),
                "n_strata": n_strata,
                "n_cases": int(y.sum()),
                "n_controls": int(len(y) - y.sum()),
                "loglikelihood": loglik,
                "converged": True,
                "iterations": iterations,
                "levels": level_labels,
            },
        )
        self._export = {
            "terms": list(covariates),
            "coef": [float(value) for value in beta],
            "se": [float(value) for value in se],
            "z": [float(value) for value in zvalues],
            "p": [float(value) for value in pvalues],
            "ci_low": [float(value) for value in ci_low],
            "ci_high": [float(value) for value in ci_high],
            "odds_ratio": [float(value) for value in odds_ratios],
            "n": int(len(y)),
            "n_strata": n_strata,
            "n_cases": int(y.sum()),
            "n_controls": int(len(y) - y.sum()),
            "loglikelihood": loglik,
            "iterations": iterations,
            "levels": level_labels,
        }
        print(
            f"[{self.name}] n={len(y)}, strata={n_strata}, "
            f"cases={int(y.sum())}, terms={len(covariates)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
