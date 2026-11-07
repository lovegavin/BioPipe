"""B-spline regression with a cubic basis."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = [
    "x",
    "y",
    "fitted",
    "residual",
    "se_mean",
    "ci_low",
    "ci_high",
]


class SplineRegressionStep(Step):
    provider = 'operon-core'
    """Fit an ordinary least-squares model on a cubic B-spline basis.

    The basis is built with :func:`patsy.bs`, which uses the same quantile
    knots as R's ``splines::bs`` for a given number of degrees of freedom.
    """
    parameters_file = 'spline_regression.SplineRegressionStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'spline_regression',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'B-spline regression',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'pandas>=2.0', 'patsy>=0.5', 'statsmodels>=0.14'],
     'dependency_imports': ['numpy', 'pandas', 'patsy', 'statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Fit an ordinary least-squares model on a cubic B-spline basis.'}


    def run(self, ctx: Context, inputs) -> None:
        import patsy
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictor_label = ctx.step_params["predictor_label"]
        df = int(ctx.step_params.get("df", 4))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if response_label == predictor_label:
            raise StepError(
                f"{self.name}: response and predictor must be different columns"
            )
        if not 4 <= df <= 10:
            raise StepError(f"{self.name}: df must be in 4..10")
        if not 0.0 < confidence < 1.0:
            raise StepError(f"{self.name}: confidence must be in (0, 1)")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        x = numeric_column(frame, predictor_label, self.name)
        y = numeric_column(frame, response_label, self.name)
        keep = np.isfinite(x) & np.isfinite(y)
        x = np.asarray(x[keep], dtype=np.float64)
        y = np.asarray(y[keep], dtype=np.float64)
        samples = (
            frame.loc[keep, "__sample__"].astype(str).to_numpy().tolist()
        )
        n = int(x.size)
        if n < df + 2:
            raise StepError(
                f"{self.name}: need at least df + 2 complete observations"
            )
        if np.ptp(x) <= 0:
            raise StepError(f"{self.name}: predictor must vary")

        try:
            basis = patsy.bs(
                x,
                df=df,
                degree=3,
                include_intercept=False,
            )
            design = sm.add_constant(
                np.asarray(basis, dtype=np.float64),
                has_constant="add",
            )
        except (ValueError, TypeError) as exc:
            raise StepError(f"{self.name}: could not build spline basis: {exc}") from exc
        if design.shape[1] < 2:
            raise StepError(f"{self.name}: spline basis has no columns")
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: spline design matrix is rank deficient")

        try:
            result = sm.OLS(y, design).fit()
            prediction = result.get_prediction(design).summary_frame(
                alpha=1.0 - confidence
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: spline fit failed: {exc}") from exc

        fitted = np.asarray(result.fittedvalues, dtype=np.float64)
        residual = np.asarray(result.resid, dtype=np.float64)
        se_mean = np.asarray(prediction["mean_se"], dtype=np.float64)
        ci_low = np.asarray(prediction["mean_ci_lower"], dtype=np.float64)
        ci_high = np.asarray(prediction["mean_ci_upper"], dtype=np.float64)
        values = [x, y, fitted, residual, se_mean, ci_low, ci_high]
        if not all(np.isfinite(value).all() for value in values):
            raise StepError(f"{self.name}: fitted values are not finite")

        n_basis = int(design.shape[1] - 1)
        boundary = [float(x.min()), float(x.max())]
        ctx[out_name] = Form(
            data=np.column_stack(values).astype(np.float64),
            dims=["sample", "statistic"],
            labels={
                "sample": {name: index for index, name in enumerate(samples)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "method": "cubic_bspline",
                "degree": 3,
                "df": df,
                "confidence": confidence,
                "n": n,
                "r2": float(result.rsquared),
                "adj_r2": float(result.rsquared_adj),
                "aic": float(result.aic),
                "bic": float(result.bic),
                "n_basis": n_basis,
                "boundary_knots": boundary,
            },
        )
        self._export = {
            "samples": samples,
            "x": x.tolist(),
            "y": y.tolist(),
            "fitted": fitted.tolist(),
            "residual": residual.tolist(),
            "se_mean": se_mean.tolist(),
            "ci_low": ci_low.tolist(),
            "ci_high": ci_high.tolist(),
            "df": df,
            "degree": 3,
            "confidence": confidence,
            "n": n,
            "r2": float(result.rsquared),
            "adj_r2": float(result.rsquared_adj),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "n_basis": n_basis,
            "boundary_knots": boundary,
        }
        print(
            f"[{self.name}] n={n}, df={df}, r2={float(result.rsquared):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
