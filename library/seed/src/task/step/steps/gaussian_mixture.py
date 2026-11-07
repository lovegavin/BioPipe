from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix

class GaussianMixtureStep(Step):
    provider = 'operon-core'
    """Gaussian mixture model clustering."""
    parameters_file = 'gaussian_mixture.GaussianMixtureStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'gaussian_mixture',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Gaussian mixture clustering',
     'category': 'Machine Learning',
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
     'dependencies': ['scikit-learn>=1.5'],
     'dependency_imports': ['sklearn'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Gaussian mixture model clustering.'}



    def run(self, ctx: Context, inputs) -> None:
        from sklearn.mixture import GaussianMixture

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_components = int(ctx.step_params.get("n_components", 2))
        covariance_type = ctx.step_params.get("covariance_type", "full")
        random_state = int(ctx.step_params.get("random_state", 0))
        max_iter = int(ctx.step_params.get("max_iter", 200))
        if n_components < 2:
            raise StepError("gaussian_mixture: n_components must be >= 2")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = GaussianMixture(
            n_components=n_components,
            covariance_type=covariance_type,
            random_state=random_state,
            max_iter=max_iter,
        )
        model.fit(X)
        labels = model.predict(X)
        probability = model.predict_proba(X).max(axis=1)
        samples = list(sample_names)
        out_name = ctx.step_params.get("output", self.name)
        data = np.column_stack([labels.astype(np.float32), probability.astype(np.float32)])
        ctx[out_name] = Form(
            data=data,
            dims=[sample_dim, "cluster"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "cluster": {"cluster": 0, "probability": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": n_components,
            "covariance_type": covariance_type,
            "bic": float(model.bic(X)),
            "aic": float(model.aic(X)),
            "converged": bool(model.converged_),
        }
        print(f"[gaussian_mixture] {len(samples)} samples -> {n_components} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
