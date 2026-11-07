"""Partial Pearson correlation after residualising both sides on covariates."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class PartialCorrelationStep(Step):
    provider = 'operon-core'
    parameters_file = 'partial_correlation.PartialCorrelationStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'partial_correlation',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Partial correlation',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'x_feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'y_feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'covariate_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 3,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Partial correlation：接收 3 个输入，输出 Form；主要参数：样本维度、X Feature Dim、Y Feature '
                    'Dim、Covariate Dim。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        x, xs, xf = matrix(inputs[0], sample_dim, ctx.step_params.get("x_feature_dim", "feature"))
        y, ys, yf = matrix(inputs[1], sample_dim, ctx.step_params.get("y_feature_dim", "feature"))
        c, cs, cf = matrix(inputs[2], sample_dim, ctx.step_params.get("covariate_dim", "feature"))
        if x.shape[1] != y.shape[1]:
            raise StepError(f"x and y need the same number of features, got {x.shape[1]} and {y.shape[1]}")
        if c.shape[1] == 0:
            raise StepError("at least one covariate is required")
        xpos = {name: i for i, name in enumerate(xs)}
        ypos = {name: i for i, name in enumerate(ys)}
        cpos = {name: i for i, name in enumerate(cs)}
        shared = [name for name in xs if name in ypos and name in cpos]
        if len(shared) <= c.shape[1] + 2:
            raise StepError(f"not enough shared samples ({len(shared)}) for {c.shape[1]} covariates")
        x = x[[xpos[name] for name in shared]]
        y = y[[ypos[name] for name in shared]]
        c = c[[cpos[name] for name in shared]]
        design = np.column_stack([np.ones(len(shared)), c])
        out = np.full((x.shape[1], 4), np.nan, dtype=np.float64)
        for j in range(x.shape[1]):
            rx = x[:, j] - design @ np.linalg.lstsq(design, x[:, j], rcond=None)[0]
            ry = y[:, j] - design @ np.linalg.lstsq(design, y[:, j], rcond=None)[0]
            if np.std(rx) == 0 or np.std(ry) == 0:
                continue
            r = float(np.corrcoef(rx, ry)[0, 1])
            df = len(shared) - c.shape[1] - 2
            if df <= 0 or abs(r) >= 1:
                t = float("inf") if abs(r) >= 1 else 0.0
                p = 0.0
            else:
                t = r * np.sqrt(df / (1.0 - r * r))
                p = 2.0 * stats.t.sf(abs(t), df)
            out[j] = (r, t, p, df)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(out, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(xf)},
                "statistic": {"r": 0, "t": 1, "p": 2, "df": 3},
            },
            info={"missing_code": np.nan, "method": "partial_pearson"},
        )
        self._export = {"n_samples": len(shared), "n_features": int(x.shape[1]), "n_covariates": int(c.shape[1])}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
