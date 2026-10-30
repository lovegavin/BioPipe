"""Mardia multivariate skewness and kurtosis tests."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import reorder
from ._stats20_common import scalar_form


class MardiaTestStep(Step):
    """Mardia's multivariate normality tests.

    Matches ``psych::mardia``: with centered data ``X`` and covariance
    ``S`` (n-1 denominator), ``D = X S^-1 X'``,
    ``b1p = sum(D^3)/n^2`` and ``b2p = trace(D^2)/n``. The skewness
    chi-square uses ``n*b1p/6`` or the small-sample correction
    ``n*k*b1p/6``; kurtosis is standardized by
    ``sqrt(n/(8*p*(p+2)))``.
    """

    name = "mardia_test"
    title = "Mardia multivariate normality test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
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
        data = reorder(form, sample_dim, feature_dim)
        keep = np.all(np.isfinite(data), axis=1)
        data = data[keep]
        n, p = data.shape
        if p < 2:
            raise StepError("mardia_test: at least two features are required")
        if n <= p + 1:
            raise StepError("mardia_test: need more complete samples than features")
        centered = data - data.mean(axis=0, keepdims=True)
        covariance = np.cov(centered, rowvar=False, ddof=1)
        try:
            inverse = np.linalg.inv(covariance)
        except np.linalg.LinAlgError as exc:
            raise StepError("mardia_test: covariance matrix is singular") from exc
        d_matrix = centered @ inverse @ centered.T
        b1p = float(np.sum(d_matrix ** 3) / n ** 2)
        b2p = float(np.sum(np.diag(d_matrix) ** 2) / n)
        chi_df = p * (p + 1) * (p + 2) / 6.0
        correction = (p + 1) * (n + 1) * (n + 3) / (n * ((n + 1) * (p + 1) - 6))
        skew = float(n * b1p / 6.0)
        small_skew = float(n * correction * b1p / 6.0)
        p_skew = float(stats.chi2.sf(skew, chi_df))
        p_small = float(stats.chi2.sf(small_skew, chi_df))
        kurtosis = float((b2p - p * (p + 2)) * np.sqrt(n / (8.0 * p * (p + 2))))
        p_kurt = float(2.0 * stats.norm.sf(abs(kurtosis)))

        values = [
            b1p, b2p, skew, small_skew, p_skew, p_small,
            kurtosis, p_kurt, chi_df, float(n), float(p),
        ]
        names = [
            "b1p", "b2p", "skew", "small_skew", "p_skew", "p_small",
            "kurtosis", "p_kurt", "chi_df", "n_samples", "n_features",
        ]
        out = scalar_form(values, names, "mardia_test")
        out.info.update({"method": "mardia", "complete_cases": int(n)})
        ctx[out_name] = out
        self._export_data = dict(zip(names, values))
        print(f"[mardia_test] b1p={b1p:.6g}, b2p={b2p:.6g}, p_skew={p_skew:.6g}, p_kurt={p_kurt:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
