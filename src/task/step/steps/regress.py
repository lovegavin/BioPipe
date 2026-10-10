# src/task/step/steps/regress.py
"""Multiple regression over one dimension of a wide form.

Input is a single wide form. One position along a chosen dimension is
the response; a set of other positions are covariates; all remaining
positions are tested one at a time as predictors.

For each predictor, the operator fits:

    response ~ predictor + covariates

Failure policy
--------------
A predictor is skipped, with a recorded reason, only when a known
condition prevents a meaningful fit:

* too few valid samples
* predictor is constant
* binary response has a single class in this subset
* design matrix is rank-deficient
* logistic fit hits perfect separation
* the fit returned non-finite estimates

Any other exception propagates. Nothing is silently swallowed.
"""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from statsmodels.tools.sm_exceptions import PerfectSeparationError

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class RegressStep(Step):
    """Regression of a response on each predictor, adjusting for covariates.

    Params:
        dim        : dimension to iterate over
        response   : label of the response column
        covariates : labels of covariates (optional)
        method     : "ols" | "logit" | "auto" (default)
        output     : context key for the result
    """

    name = "regress"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]

        dim = ctx.step_params["dim"]
        response_label = ctx.step_params["response"]
        covariate_labels = list(ctx.step_params.get("covariates", []))
        method = ctx.step_params.get("method", "auto")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2:
            raise StepError(
                f"regress requires a 2D form, got ndim={form.data.ndim}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' not present. Available: {form.dims}"
            )

        feature_axis = form.dims.index(dim)
        obs_axis = 1 - feature_axis
        n_obs = form.data.shape[obs_axis]

        feature_labels = form.labels.get(dim, {})
        if not feature_labels:
            raise StepError(
                f"Dim '{dim}' has no labels. "
                f"Label the columns before running regress."
            )

        if response_label not in feature_labels:
            raise StepError(
                f"Response '{response_label}' not in dim '{dim}'. "
                f"Available: {sorted(feature_labels)}"
            )
        response_pos = feature_labels[response_label]

        cov_positions: list[int] = []
        for c in covariate_labels:
            if c == response_label:
                raise StepError(
                    f"Covariate '{c}' equals response '{response_label}'"
                )
            if c not in feature_labels:
                raise StepError(
                    f"Covariate '{c}' not in dim '{dim}'. "
                    f"Available: {sorted(feature_labels)}"
                )
            cov_positions.append(feature_labels[c])

        excluded = {response_pos, *cov_positions}
        predictors = sorted(
            ((label, pos) for label, pos in feature_labels.items()
             if pos not in excluded),
            key=lambda kv: kv[1],
        )
        if not predictors:
            raise StepError(
                "regress: no predictor columns remain after excluding "
                "response and covariates."
            )

        y = np.take(form.data, response_pos, axis=feature_axis).astype(float)
        y_missing = _missing_mask(y, form.info.get("missing_code", np.nan))

        if cov_positions:
            cov_block = np.stack(
                [
                    np.take(form.data, p, axis=feature_axis).astype(float)
                    for p in cov_positions
                ],
                axis=1,
            )
            cov_missing_per_row = np.isnan(cov_block).any(axis=1)
        else:
            cov_block = None
            cov_missing_per_row = np.zeros(n_obs, dtype=bool)

        y_obs = y[~y_missing]
        if y_obs.size == 0:
            raise StepError("regress: response is entirely missing")
        if method == "auto":
            binary = len(np.unique(y_obs)) == 2
        elif method == "logit":
            binary = True
        elif method == "ols":
            binary = False
        else:
            raise StepError(
                f"regress: method must be 'ols', 'logit' or 'auto', "
                f"got {method!r}"
            )

        result = np.full((len(predictors), 4), np.nan, dtype=float)
        failures: list[tuple[str, str]] = []
        per_row: list[dict] = []

        for i, (label, pos) in enumerate(predictors):
            x = np.take(form.data, pos, axis=feature_axis).astype(float)
            x_missing = _missing_mask(
                x, form.info.get("missing_code", np.nan)
            )

            valid = ~(x_missing | y_missing | cov_missing_per_row)
            n_valid = int(valid.sum())

            if n_valid < 3:
                failures.append(
                    (label, f"only {n_valid} valid samples")
                )
                per_row.append({
                    "label": label,
                    "skipped": f"only {n_valid} valid samples",
                })
                continue

            x_sub = x[valid]
            y_sub = y[valid]

            if x_sub.std() < 1e-12:
                failures.append((label, "predictor is constant"))
                per_row.append({
                    "label": label,
                    "skipped": "predictor is constant",
                })
                continue

            if binary and len(np.unique(y_sub)) < 2:
                failures.append(
                    (label, "binary response has a single class")
                )
                per_row.append({
                    "label": label,
                    "skipped": "binary response has a single class",
                })
                continue

            design = x_sub.reshape(-1, 1)
            if cov_block is not None:
                design = np.hstack([design, cov_block[valid]])
            design = sm.add_constant(design, has_constant="add")

            if np.linalg.matrix_rank(design) < design.shape[1]:
                failures.append(
                    (label, "design matrix is rank-deficient")
                )
                per_row.append({
                    "label": label,
                    "skipped": "design matrix is rank-deficient",
                })
                continue

            if binary:
                y_bin = (y_sub > y_sub.min()).astype(float)
                try:
                    fit = sm.Logit(y_bin, design).fit(
                        disp=0, maxiter=100
                    )
                except PerfectSeparationError:
                    failures.append((label, "perfect separation"))
                    per_row.append({
                        "label": label,
                        "skipped": "perfect separation",
                    })
                    continue
            else:
                fit = sm.OLS(y_sub, design).fit()

            beta = float(fit.params[1])
            se = float(fit.bse[1])
            pval = float(fit.pvalues[1])

            if not (np.isfinite(beta) and np.isfinite(se)
                    and np.isfinite(pval)):
                failures.append((label, "non-finite estimate"))
                per_row.append({
                    "label": label,
                    "skipped": "non-finite estimate",
                })
                continue

            result[i] = [beta, se, pval, n_valid]
            per_row.append({
                "label": label,
                "beta": beta,
                "se": se,
                "p": pval,
                "n": n_valid,
            })

        out_labels_dim = {
            label: i for i, (label, _) in enumerate(predictors)
        }

        ctx[out_name] = Form(
            data=result.astype(np.float32),
            dims=[dim, "statistic"],
            labels={
                dim: out_labels_dim,
                "statistic": {"BETA": 0, "SE": 1, "P": 2, "N": 3},
            },
            info={},
        )

        n_tested = int(np.isfinite(result[:, 2]).sum())

        self._export_data = {
            "dim": dim,
            "response": response_label,
            "covariates": list(covariate_labels),
            "binary": bool(binary),
            "n_observations": n_obs,
            "n_predictors": len(predictors),
            "n_tested": n_tested,
            "n_failed": len(failures),
            "results": per_row,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "response": response_label,
            "covariates": list(covariate_labels),
            "binary": bool(binary),
            "n_predictors": len(predictors),
            "n_tested": n_tested,
            "n_failed": len(failures),
            "n_obs": n_obs,
        }

        msg = (
            f"[regress] dim='{dim}' response='{response_label}' "
            f"covariates={covariate_labels} "
            f"tested {n_tested}/{len(predictors)} "
            f"({'binary' if binary else 'continuous'})"
        )
        if failures:
            msg += f", {len(failures)} skipped"
        print(msg)

        if failures:
            for lab, why in failures[:5]:
                print(f"  skipped {lab}: {why}")
            if len(failures) > 5:
                print(
                    f"  ... and {len(failures) - 5} more "
                    f"(see output/steps/)"
                )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _missing_mask(arr: np.ndarray, code) -> np.ndarray:
    if code is None:
        return np.zeros(arr.shape, dtype=bool)
    if isinstance(code, float) and np.isnan(code):
        return np.isnan(arr)
    return arr == code