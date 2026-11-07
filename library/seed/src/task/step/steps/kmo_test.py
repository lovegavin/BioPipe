"""Kaiser-Meyer-Olkin measure of sampling adequacy."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._factorability36_common import correlation_matrix
from ._stats20_common import scalar_form


class KmoTestStep(Step):
    provider = 'operon-core'
    """KMO overall and per-variable measures of sampling adequacy."""
    parameters_file = 'kmo_test.KmoTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'kmo_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'KMO sampling adequacy',
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'KMO overall and per-variable measures of sampling adequacy.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        correlation, names, n = correlation_matrix(
            form, sample_dim, feature_dim, "kmo_test"
        )
        try:
            inverse = np.linalg.inv(correlation)
        except np.linalg.LinAlgError as exc:
            raise StepError("kmo_test: correlation matrix is singular") from exc
        scale = np.sqrt(np.diag(inverse))
        if np.any(scale <= 0):
            raise StepError("kmo_test: invalid inverse correlation diagonal")
        partial = -inverse / np.outer(scale, scale)
        np.fill_diagonal(partial, 0.0)
        r2 = np.square(correlation)
        np.fill_diagonal(r2, 0.0)
        p2 = np.square(partial)
        denominator = r2.sum() + p2.sum()
        if denominator <= 0:
            raise StepError("kmo_test: no off-diagonal correlation")
        overall = float(r2.sum() / denominator)
        row_sums = r2.sum(axis=0)
        per_variable = row_sums / (row_sums + p2.sum(axis=0))

        values = [overall] + [float(value) for value in per_variable]
        labels = ["MSA_overall"] + [f"MSA:{name}" for name in names]
        out = scalar_form(values, labels, "kmo")
        out.info.update(
            {
                "n_subjects": int(n),
                "n_variables": len(names),
                "variables": names,
                "msa_overall": overall,
                "msa": {name: float(value) for name, value in zip(names, per_variable)},
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "msa_overall": overall,
            "msa": {name: float(value) for name, value in zip(names, per_variable)},
            "n_subjects": int(n),
            "n_variables": len(names),
            "variables": names,
        }
        print(f"[kmo_test] MSA={overall:.6f}, p={len(names)}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
