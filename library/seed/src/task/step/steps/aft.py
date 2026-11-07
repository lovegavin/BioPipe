"""Weibull accelerated failure time regression."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


class AftStep(Step):
    provider = 'operon-core'
    """Weibull accelerated failure time model with right censoring."""
    parameters_file = 'aft.AftStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'aft',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Weibull accelerated failure time',
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
     'dependencies': ['lifelines<0.31,>=0.30'],
     'dependency_imports': ['lifelines'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Weibull accelerated failure time model with right censoring.'}


    def run(self, ctx: Context, inputs) -> None:
        try:
            from lifelines import WeibullAFTFitter
            from scipy.stats import norm
        except ImportError as exc:
            raise StepError(f"{self.name}: lifelines is required") from exc

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        time_label = ctx.step_params["time_label"]
        event_label = ctx.step_params["event_label"]
        covariates = list(ctx.step_params["covariates"])
        categorical = list(ctx.step_params.get("categorical", []))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        missing = [name for name in categorical if name not in covariates]
        if missing:
            raise StepError(f"{self.name}: categorical names not in covariates: {missing}")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        for name in [time_label, event_label, *covariates]:
            if name not in frame.columns:
                raise StepError(f"{self.name}: column {name!r} not found")

        times = numeric_column(frame, time_label, self.name)
        events = numeric_column(frame, event_label, self.name)
        design, terms = design_matrix(frame, covariates, categorical, self.name)
        keep = (
            np.isfinite(times)
            & np.isfinite(events)
            & np.isfinite(design).all(axis=1)
        )
        times = times[keep]
        events = events[keep]
        design = design[keep]
        if times.size < 10:
            raise StepError(f"{self.name}: at least 10 complete observations are required")
        if np.any(times <= 0):
            raise StepError(f"{self.name}: follow-up times must be positive")
        if not np.all(np.isin(events, [0.0, 1.0])):
            raise StepError(f"{self.name}: event column must contain only 0/1")
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(f"{self.name}: design matrix is rank deficient")
        if int(events.sum()) < 2:
            raise StepError(f"{self.name}: at least two events are required")

        covariate_terms = terms[1:]
        fit_frame = pd.DataFrame(design[:, 1:], columns=covariate_terms)
        fit_frame.insert(0, "__duration__", times)
        fit_frame.insert(1, "__event__", events)
        try:
            fit = WeibullAFTFitter().fit(
                fit_frame,
                duration_col="__duration__",
                event_col="__event__",
            )
        except Exception as exc:
            raise StepError(f"{self.name}: fit failed: {exc}") from exc

        summary = fit.summary
        zcrit = float(norm.ppf(1.0 - (1.0 - confidence) / 2.0))
        rows = []
        export_terms = []
        coefs = []
        ses = []
        zs = []
        ps = []
        for term in ["Intercept", *covariate_terms]:
            try:
                row = summary.loc[("lambda_", term)]
            except KeyError as exc:
                raise StepError(f"{self.name}: coefficient {term!r} missing from fit") from exc
            coef = float(row["coef"])
            se = float(row["se(coef)"])
            z = coef / se if np.isfinite(se) and se > 0 else float("nan")
            p = float(row["p"])
            low = coef - zcrit * se
            high = coef + zcrit * se
            rows.append([coef, se, z, p, low, high, float(np.exp(coef))])
            export_terms.append(term)
            coefs.append(coef)
            ses.append(se)
            zs.append(z)
            ps.append(p)

        rho = float(summary.loc[("rho_", "Intercept"), "coef"])
        shape = float(np.exp(rho))
        scale = 1.0 / shape
        block = np.asarray(rows, dtype=np.float32)
        ctx[out_name] = Form(
            data=block,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(export_terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                    "time_ratio": 6,
                },
            },
            info={
                "method": "Weibull AFT",
                "distribution": "weibull",
                "n": int(times.size),
                "events": int(events.sum()),
                "censored": int(times.size - events.sum()),
                "shape": shape,
                "scale": scale,
                "loglik": float(fit.log_likelihood_),
                "terms": export_terms,
                "confidence": confidence,
            },
        )
        self._export = {
            "terms": export_terms,
            "coef": coefs,
            "se": ses,
            "z": zs,
            "p": ps,
            "time_ratio": [float(np.exp(value)) for value in coefs],
            "shape": shape,
            "scale": scale,
            "loglik": float(fit.log_likelihood_),
            "n": int(times.size),
            "events": int(events.sum()),
        }
        print(f"[{self.name}] n={times.size}, events={int(events.sum())}, terms={len(export_terms)}")

    def export(self, ctx: Context) -> dict:
        return self._export
