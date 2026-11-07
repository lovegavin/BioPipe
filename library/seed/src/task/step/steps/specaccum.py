"""Species accumulation curve with the exact (rarefaction) expectation.

For each number of sites ``i`` the expected number of species is

    richness(i) = sum_s (1 - C(n - freq_s, i) / C(n, i))

where ``freq_s`` is the number of sites in which species ``s`` occurs
and ``C`` is the binomial coefficient. The conditioned standard
deviation follows ``vegan::specaccum(method = "exact", conditioned = TRUE)``:

    var(i) = sum_s p_is (1 - p_is) + 2 * sum_{s < t} r_st sqrt(var_s var_t)

with ``p_is`` the probability that species ``s`` is present in a random
subset of ``i`` sites and ``r_st`` the correlation of the two presence
indicators over all sites.

The operator reads only the abundance table: a taxon counts as present
when its value is greater than zero (``colSums(x > 0)``).
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ecology_common import abundance


class SpecaccumStep(Step):
    """Expected species richness as a function of the number of sites."""

    provider = 'operon-microbiome'
    parameters_file = 'specaccum.SpecaccumStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'specaccum',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Species accumulation',
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Exact species accumulation curve and its conditioned standard deviation.'}

    def run(self, ctx: Context, inputs) -> None:
        table_form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        data, samples, taxa = abundance(table_form, sample_dim, taxon_dim, "specaccum")
        n_sites = data.shape[0]
        if n_sites < 2:
            raise StepError("specaccum: need at least two sampling units")
        present = data > 0.0
        if not np.any(present):
            raise StepError("specaccum: every sample is empty (no taxon has a positive count)")
        frequency = present.sum(axis=0).astype(np.int64)

        steps = np.arange(1, n_sites + 1)
        from math import lgamma
        ldiv = np.asarray([lgamma(n_sites + 1) - lgamma(i + 1) - lgamma(n_sites - i + 1)
                           for i in steps], dtype=np.float64)
        absence = np.zeros((n_sites, frequency.size), dtype=np.float64)
        for row, i in enumerate(steps):
            available = n_sites - frequency
            keep = available >= i
            if np.any(keep):
                numerator = np.asarray(
                    [lgamma(n_sites - frequency[s] + 1)
                     - lgamma(i + 1)
                     - lgamma(n_sites - frequency[s] - i + 1)
                     for s in np.flatnonzero(keep)],
                    dtype=np.float64,
                )
                absence[row, keep] = np.exp(numerator - ldiv[row])
        richness = np.sum(1.0 - absence, axis=1)

        variance = absence * (1.0 - absence)
        if frequency.size > 1:
            corr = np.corrcoef(present, rowvar=False)
            corr = np.where(np.isfinite(corr), corr, 0.0)
            lower = np.tril_indices(frequency.size, -1)
            corr_lower = corr[lower]
            sd = np.zeros(n_sites, dtype=np.float64)
            for row in range(n_sites):
                block = np.sqrt(variance[row][:, None] * variance[row][None, :])
                covariance = 2.0 * np.sum(corr_lower * block[lower])
                total = np.sum(variance[row]) + covariance
                # vegan can report NaN here when round-off makes the exactly
                # zero variance slightly negative; clamp that artifact to zero.
                sd[row] = float(np.sqrt(total)) if total > 0.0 else 0.0
        else:
            sd = np.sqrt(np.sum(variance, axis=1))

        values = np.column_stack([richness, sd]).astype(np.float32)
        out = Form(
            data=values,
            dims=["sites", "statistic"],
            labels={
                "sites": {str(i + 1): i for i in range(n_sites)},
                "statistic": {"richness": 0, "sd": 1},
            },
            info={
                "missing_code": np.nan,
                "method": "exact",
                "conditioned": True,
                "n_sites": int(n_sites),
                "n_species": int(frequency.size),
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "n_sites": int(n_sites),
            "n_species": int(frequency.size),
            "richness": [float(value) for value in richness],
            "sd": [float(value) for value in sd],
            "final_richness": float(richness[-1]),
        }
        print(f"[{self.name}] final_richness={richness[-1]:.6f}")

    def export(self, ctx: Context) -> dict:
        return self._export
