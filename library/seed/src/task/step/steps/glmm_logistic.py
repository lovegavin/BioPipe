"""Logistic mixed model with a single random intercept (Laplace)."""
from __future__ import annotations

import numpy as np
from scipy import optimize, stats as sps

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import group_values


def _loglik(params, x, y, codes, n_groups):
    beta = params[:2]
    sigma = float(np.exp(params[2]))
    eta = x @ beta
    loglik = 0.0
    for g in range(n_groups):
        mask = codes == g
        yy = y[mask]
        e = eta[mask]
        u = 0.0
        for _ in range(100):
            p = 1.0 / (1.0 + np.exp(-(e + u)))
            grad = float(np.sum(yy - p) - u / sigma ** 2)
            hess = float(np.sum(p * (1.0 - p)) + 1.0 / sigma ** 2)
            step = grad / hess
            u += step
            if abs(step) < 1e-10:
                break
        p = 1.0 / (1.0 + np.exp(-(e + u)))
        loglik += float(np.sum(yy * (e + u) - np.log1p(np.exp(e + u))))
        loglik -= u * u / (2.0 * sigma ** 2)
        hess = float(np.sum(p * (1.0 - p)) + 1.0 / sigma ** 2)
        loglik -= 0.5 * np.log(2.0 * np.pi * sigma ** 2)
        loglik -= 0.5 * np.log(hess)
    return loglik + 0.5 * n_groups * np.log(2.0 * np.pi)


class GlmmLogisticStep(Step):
    provider = "operon-core"
    parameters_file = "glmm_logistic.GlmmLogisticStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "glmm_logistic",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Logistic mixed model",
        "category": "Statistics",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "feature_dim", "default": "feature"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "group_dim", "default": "feature"}],
                 "labels": [], "parallel": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26", "scipy>=1.11"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Binary logistic regression with a random intercept fitted by "
            "Laplace approximation (lme4 glmer nAGQ=1)."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        table, meta = inputs
        if meta.dims[0] != ctx.step_params.get("sample_dim", "sample") or ctx.step_params.get("group_dim", "feature") not in meta.dims:
            raise StepError("glmm_logistic: group table must be [sample, group_dim]")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        target_label = ctx.step_params["target_label"]
        predictor_label = ctx.step_params["predictor_label"]
        group_label = ctx.step_params["group_label"]
        out_name = ctx.step_params.get("output", self.name)

        if table.dims[0] != sample_dim or feature_dim not in table.dims:
            raise StepError(
                f"glmm_logistic: table must be [{sample_dim}, {feature_dim}], "
                f"got {table.dims}"
            )
        columns = table.labels[feature_dim]
        for name in (target_label, predictor_label):
            if name not in columns:
                raise StepError(
                    f"glmm_logistic: column {name!r} not in {sorted(columns)}"
                )
        names, groups = group_values(meta, sample_dim, group_label)
        table_names = table.labels[sample_dim]
        common = [name for name in table_names if name in set(names)]
        if len(common) < 8:
            raise StepError(
                f"glmm_logistic: only {len(common)} shared samples"
            )
        row_of = {name: i for i, name in enumerate(table_names)}
        rows = [row_of[name] for name in common]
        y_col = columns[target_label]
        x_col = columns[predictor_label]
        data = np.asarray(table.data, dtype=np.float64)[rows, :]
        y = data[:, y_col]
        x = data[:, x_col]
        group_of = dict(zip(names, groups))
        labels = [group_of[name] for name in common]
        keep = (np.isfinite(y) & np.isfinite(x)
                & np.array([g is not None for g in labels]))
        y = y[keep]
        x = x[keep]
        labels = [g for g, k in zip(labels, keep) if k]
        if not np.all(np.isin(y, (0.0, 1.0))):
            raise StepError("glmm_logistic: outcome must be binary 0/1")
        levels = sorted(set(labels))
        if len(levels) < 2:
            raise StepError("glmm_logistic: need at least two groups")
        ids = {level: i for i, level in enumerate(levels)}
        codes = np.array([ids[g] for g in labels], dtype=int)
        n_groups = len(levels)
        counts = np.bincount(codes)
        if counts.min() < 2:
            raise StepError(
                f"glmm_logistic: every group needs >= 2 samples, got "
                f"{counts.tolist()}"
            )
        if np.ptp(x) <= 0:
            raise StepError("glmm_logistic: predictor is constant")
        design = np.column_stack([np.ones_like(x), x])
        n_obs = y.size

        def objective(params):
            return -_loglik(params, design, y, codes, n_groups)

        start = np.array([0.0, 0.0, np.log(0.7)])
        result = optimize.minimize(
            objective, start, method="BFGS",
            options={"gtol": 1e-9, "maxiter": 2000},
        )
        if not result.success and result.status not in (1, 2):
            raise StepError(
                f"glmm_logistic: optimizer failed: {result.message}"
            )
        beta = result.x[:2]
        sigma = float(np.exp(result.x[2]))
        if not (np.all(np.isfinite(beta)) and np.isfinite(sigma)
                and sigma > 0):
            raise StepError("glmm_logistic: fit produced invalid estimates")

        def gradient(theta):
            base = float(objective(theta))
            values = np.zeros_like(theta)
            for i in range(theta.size):
                step = 1e-5 * max(1.0, abs(theta[i]))
                shifted = theta.copy()
                shifted[i] += step
                values[i] = (objective(shifted) - base) / step
            return values

        hessian = np.zeros((3, 3))
        step = 1e-4
        grad0 = gradient(result.x)
        for i in range(3):
            shifted = result.x.copy()
            shifted[i] += step
            hessian[:, i] = (gradient(shifted) - grad0) / step
        cov = np.linalg.pinv(hessian)
        se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
        z_value = beta / se[:2]
        p_value = 2.0 * sps.norm.sf(np.abs(z_value))
        z_crit = float(sps.norm.ppf(0.975))
        rows_out = ["(Intercept)", predictor_label, "sigma", "loglik"]
        stats_out = [
            [beta[0], se[0], z_value[0], p_value[0],
             beta[0] - z_crit * se[0], beta[0] + z_crit * se[0]],
            [beta[1], se[1], z_value[1], p_value[1],
             beta[1] - z_crit * se[1], beta[1] + z_crit * se[1]],
            [sigma, np.nan, np.nan, np.nan, np.nan, np.nan],
            [-float(result.fun), np.nan, np.nan, np.nan, np.nan, np.nan],
        ]
        ctx[out_name] = Form(
            data=np.asarray(stats_out, dtype=np.float32),
            dims=["term", "statistic"],
            labels={"term": {name: i for i, name in enumerate(rows_out)},
                    "statistic": {"estimate": 0, "se": 1, "z": 2,
                                  "p_value": 3, "ci_low": 4, "ci_high": 5}},
            info={"missing_code": np.nan, "families": ["binomial"],
                  "n_groups": int(n_groups), "n_samples": int(n_obs),
                  "method": "laplace"},
        )
        self._export_data = {
            "coef": {"(Intercept)": float(beta[0]),
                     predictor_label: float(beta[1])},
            "se": {"(Intercept)": float(se[0]),
                   predictor_label: float(se[1])},
            "sigma": sigma,
            "loglik": -float(result.fun),
            "n_groups": int(n_groups),
            "n_samples": int(n_obs),
        }
        print(f"[{self.name}] beta={beta[1]:.4f} sigma={sigma:.4f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
