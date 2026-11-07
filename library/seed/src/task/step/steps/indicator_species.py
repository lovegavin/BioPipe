"""Indicator species analysis (Dufrene-Legendre IndVal).

For each taxon and group the operator reports the fidelity
(proportion of group samples where the taxon is present), the
specificity (group mean abundance divided by the sum of group means)
and their product, matching ``labdsv::indval`` with
``permutations = 0``. No permutation p-value is produced.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ecology_common import abundance, group_codes


class IndicatorSpeciesStep(Step):
    """Per-taxon IndVal scores for every group in a metadata column."""

    provider = 'operon-microbiome'
    parameters_file = 'indicator_species.IndicatorSpeciesStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'indicator_species',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Indicator species',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'taxon_dim', 'default': 'taxon'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        'feature'],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Indicator species (IndVal) fidelity, specificity and product per group.'}

    def run(self, ctx: Context, inputs) -> None:
        table_form, meta_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_label = ctx.step_params["group_label"]

        data, samples, taxa = abundance(table_form, sample_dim, taxon_dim, "indicator_species")
        codes = group_codes(meta_form, sample_dim, group_label, samples, "indicator_species")
        groups = sorted(set(codes.tolist()))
        if len(groups) < 2:
            raise StepError("indicator_species: need at least two groups")
        if (data.sum(axis=0) <= 0.0).any():
            raise StepError(
                "indicator_species: every taxon must occur in at least one sample"
            )

        means = np.column_stack([data[codes == group].mean(axis=0) for group in groups])
        totals = means.sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            specificity = np.where(totals[:, None] > 0.0, means / totals[:, None], 0.0)
        fidelity = np.column_stack([
            (data[codes == group] > 0.0).mean(axis=0) for group in groups
        ])
        indval = specificity * fidelity
        best = indval.argmax(axis=1)
        best_values = indval[np.arange(indval.shape[0]), best]

        columns = []
        names = []
        for index, group in enumerate(groups):
            columns.extend([fidelity[:, index], specificity[:, index], indval[:, index]])
            names.extend(
                [f"fidelity:{group}", f"specificity:{group}", f"indval:{group}"]
            )
        columns.extend([best_values, best.astype(np.float64)])
        names.extend(["indval_max", "group_max"])
        values = np.column_stack(columns)

        out = Form(
            data=np.asarray(values, dtype=np.float32),
            dims=["taxon", "statistic"],
            labels={
                "taxon": {name: position for position, name in enumerate(taxa)},
                "statistic": {name: position for position, name in enumerate(names)},
            },
            info={
                "missing_code": np.nan,
                "method": "indval",
                "groups": list(groups),
                "n_groups": len(groups),
                "p_value": "not computed",
            },
        )
        out.validate()
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "groups": list(groups),
            "n_taxa": len(taxa),
            "max_indval": float(best_values.max()) if best_values.size else 0.0,
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export", {})
