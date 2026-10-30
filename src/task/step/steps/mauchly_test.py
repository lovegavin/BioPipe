"""Mauchly's test of sphericity for a multivariate normal sample."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import reorder
from ._stats20_common import scalar_form


class MauchlyTestStep(Step):
    """Mauchly's sphericity test with the chi-square approximation."""

    name = "mauchly_test"
    title = "Mauchly's sphericity test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
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
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        try:
            values = reorder(form, sample_dim, feature_dim).astype(np.float64)
        except (TypeError, ValueError) as exc:
            raise StepError("mauchly_test: every feature must be numeric") from exc
        if values.ndim != 2:
            raise StepError("mauchly_test: input must be two-dimensional")
        n, p = values.shape
        if p < 3:
            raise StepError("mauchly_test: at least three features are required")
        if n <= p:
            raise StepError("mauchly_test: sample count must exceed feature count")
        if not np.all(np.isfinite(values)):
            raise StepError("mauchly_test: missing or non-finite values are not supported")
        covariance = np.cov(values, rowvar=False, ddof=1)
        sign, logdet = np.linalg.slogdet(covariance)
        if sign <= 0 or not np.isfinite(logdet):
            raise StepError("mauchly_test: covariance matrix is singular")
        trace = float(np.trace(covariance))
        if trace <= 0:
            raise StepError("mauchly_test: covariance matrix has zero trace")
        q = p
        log_w = float(logdet - q * np.log(trace / q))
        w_value = float(np.exp(log_w))
        df = n - 1
        rho = 1.0 - (2.0 * q * q + q + 2.0) / (6.0 * q * df)
        if rho <= 0:
            raise StepError("mauchly_test: sample size is too small for the approximation")
        w2 = (
            (q + 2.0)
            * (q - 1.0)
            * (q - 2.0)
            * (2.0 * q**3 + 6.0 * q * q + 3.0 * p + 2.0)
            / (288.0 * (df * q * rho) ** 2)
        )
        chi2 = float(-df * rho * log_w)
        chi_df = q * (q + 1.0) / 2.0 - 1.0
        p_value = float(
            stats.chi2.sf(chi2, chi_df)
            + w2 * (stats.chi2.sf(chi2, chi_df + 4.0) - stats.chi2.sf(chi2, chi_df))
        )
        p_value = min(1.0, max(0.0, p_value))
        out = scalar_form(
            [w_value, chi2, chi_df, p_value, float(p), float(n)],
            ["W", "chi2", "df", "p", "n_features", "n"],
            self.name,
        )
        out.info.update(
            {
                "method": "Mauchly sphericity, chi-square approximation",
                "n_features": p,
                "n_samples": n,
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "W": w_value,
            "chi2": chi2,
            "df": chi_df,
            "p": p_value,
            "n_features": p,
            "n": n,
        }
        print(f"[{self.name}] W={w_value:.6g}, chi2={chi2:.6f}, df={chi_df:g}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
