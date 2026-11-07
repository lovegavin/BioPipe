"""t-SNE embedding.

Projects samples into two (or three) non-linear components. The
implementation calls scikit-learn's exact t-SNE; it is intended for
small and medium matrices, not for atlas-scale data.
"""
from __future__ import annotations


from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class TsneStep(Step):
    provider = 'operon-core'
    parameters_file = 'tsne.TsneStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'tsne',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 't-SNE',
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
     'description': 't-SNE：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、主成分数、Perplexity、学习率、Max Iter。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        if X.shape[0] < 3:
            raise StepError("tsne needs at least three samples")
        n = int(ctx.step_params.get("n_components", 2))
        perplexity = float(ctx.step_params.get("perplexity", 30.0))
        if perplexity >= X.shape[0]:
            raise StepError(
                f"tsne: perplexity ({perplexity}) must be smaller than n_samples ({X.shape[0]})"
            )
        from sklearn.manifold import TSNE
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        out = TSNE(
            n_components=n,
            perplexity=perplexity,
            learning_rate=ctx.step_params.get("learning_rate", "auto"),
            max_iter=int(ctx.step_params.get("max_iter", 1000)),
            random_state=int(ctx.step_params.get("random_state", 0)),
            init="pca",
        ).fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "TSNE")
        self._export_data = {"n_samples": int(X.shape[0]), "n_components": n, "perplexity": perplexity}
        print(f"[tsne] {X.shape[0]} samples -> {n} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
