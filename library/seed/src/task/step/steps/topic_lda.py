"""Latent Dirichlet allocation topic model for non-negative count data.

Each sample is a document and each feature is a token type. The
output is the sample-topic distribution. This operator is not a
gene-level LDA classifier; use lda_classifier for supervised LDA."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class TopicLdaStep(Step):
    provider = 'operon-core'
    parameters_file = 'topic_lda.TopicLdaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'topic_lda',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Topic LDA',
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
     'description': 'Topic LDA：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、主成分数、Max Iter、Learning Method、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        if np.any(X < 0):
            raise StepError("topic_lda requires non-negative input")
        if X.shape[0] < 2:
            raise StepError("topic_lda needs at least two samples")
        from sklearn.decomposition import LatentDirichletAllocation
        model = LatentDirichletAllocation(
            n_components=int(ctx.step_params.get("n_components", 2)),
            max_iter=int(ctx.step_params.get("max_iter", 20)),
            learning_method=ctx.step_params.get("learning_method", "batch"),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        embedded = model.fit_transform(X)
        projection(ctx, ctx.step_params.get("output", self.name), embedded,
                   sample_dim, samples, "Topic")
        self._export = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": int(embedded.shape[1]),
        }
        print(f"[topic_lda] {X.shape[0]} samples, {X.shape[1]} features -> {embedded.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export
