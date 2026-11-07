"""Locally linear embedding (LLE) of samples.

Uses sklearn.manifold.LocallyLinearEmbedding with a fixed
n_neighbors graph. The standard, modified, ltsa and hessian
algorithms are exposed; hessian may be numerically delicate on
small matrices."""
from __future__ import annotations


from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class LocallyLinearEmbeddingStep(Step):
    provider = 'operon-core'
    parameters_file = 'locally_linear_embedding.LocallyLinearEmbeddingStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'locally_linear_embedding',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Locally linear embedding',
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
     'description': 'Locally linear embedding：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、主成分数、邻居数、方法、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        if X.shape[0] < 4:
            raise StepError("locally_linear_embedding needs at least four samples")
        n = int(ctx.step_params.get("n_components", 2))
        k = int(ctx.step_params.get("n_neighbors", 5))
        if n >= X.shape[0]:
            raise StepError("locally_linear_embedding: n_components must be smaller than n_samples")
        if k >= X.shape[0]:
            raise StepError("locally_linear_embedding: n_neighbors must be smaller than n_samples")
        from sklearn.manifold import LocallyLinearEmbedding
        model = LocallyLinearEmbedding(
            n_components=int(ctx.step_params.get("n_components", 2)),
            n_neighbors=int(ctx.step_params.get("n_neighbors", 5)),
            method=ctx.step_params.get("method", "standard"),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        embedded = model.fit_transform(X)
        projection(ctx, ctx.step_params.get("output", self.name), embedded,
                   sample_dim, samples, "LLE")
        self._export = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_components": int(embedded.shape[1]),
        }
        print(f"[locally_linear_embedding] {X.shape[0]} samples, {X.shape[1]} features -> {embedded.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export
