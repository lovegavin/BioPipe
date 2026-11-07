"""Projection operator based on scikit-learn's Factor analysis."""
from __future__ import annotations


from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix, projection


class FactorAnalysisStep(Step):
    provider = 'operon-core'
    parameters_file = 'factor_analysis.FactorAnalysisStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'factor_analysis',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Factor analysis',
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
     'description': 'Factor analysis：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、主成分数、Max Iter。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, samples, _features = matrix(form, sample_dim, feature_dim)
        k = int(ctx.step_params.get("n_components", 2))
        if k < 1:
            raise StepError("n_components must be >= 1")
        from sklearn.decomposition import FactorAnalysis
        from sklearn.preprocessing import StandardScaler

        Xs = StandardScaler().fit_transform(X)
        model = FactorAnalysis(
            n_components=k,
            max_iter=int(ctx.step_params.get("max_iter", 1000)),
            random_state=int(ctx.step_params.get("random_state", 0)),
        )
        out = model.fit_transform(Xs)
        projection(ctx, ctx.step_params.get("output", self.name), out, sample_dim, samples, "Factor")
        self._export_data = {"n_samples": int(X.shape[0]), "n_components": int(out.shape[1])}
        print(f"[factor_analysis] {X.shape[0]}x{X.shape[1]} -> {out.shape[1]} components")

    def export(self, ctx: Context) -> dict:
        return self._export_data
