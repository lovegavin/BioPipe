"""Fisher's alpha diversity index."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._ecology_common import abundance


def _fisher_alpha(counts: np.ndarray) -> float:
    positive = counts[counts > 0.0]
    species = int(positive.size)
    individuals = float(positive.sum())
    if species == 0:
        return 0.0
    if species >= individuals:
        return float("inf")

    def equation(alpha: float) -> float:
        return alpha * np.log1p(individuals / alpha) - species

    low = 1e-12
    high = max(individuals, 1.0)
    while equation(high) < 0.0:
        high *= 2.0
    return float(brentq(equation, low, high, xtol=1e-13, rtol=1e-14))


class FisherAlphaStep(Step):
    """Fisher's log-series alpha for each sample.

    ``alpha`` solves ``alpha * log(1 + N / alpha) = S`` where ``S`` is the
    number of observed taxa and ``N`` the number of individuals. Samples that
    contain only singletons have no finite solution and report ``inf``.
    """

    provider = 'operon-microbiome'

    parameters_file = 'fisher_alpha.FisherAlphaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fisher_alpha',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Fisher's alpha",
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'taxon_dim', 'default': 'taxon'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Fisher's log-series alpha diversity for each sample."}

    def run(self, ctx: Context, inputs) -> None:
        (table,) = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        data, samples, _taxa = abundance(table, sample_dim, taxon_dim, "fisher_alpha")

        values = [_fisher_alpha(row) for row in data]
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(values, dtype=np.float32).reshape(-1, 1),
            dims=["sample", "statistic"],
            labels={
                "sample": {name: index for index, name in enumerate(samples)},
                "statistic": {"alpha": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "fisher_alpha",
                "n_species": [int(np.count_nonzero(row > 0.0)) for row in data],
                "n_individuals": [float(row.sum()) for row in data],
            },
        )
        self._export_data = {
            "n_samples": len(samples),
            "alpha": [float(value) for value in values],
        }
        print(f"[fisher_alpha] {len(samples)} samples")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
