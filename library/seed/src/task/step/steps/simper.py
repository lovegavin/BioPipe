"""SIMPER: similarity percentages between two groups.

For samples i (group A) and j (group B) the Bray-Curtis
dissimilarity is decomposed into per-taxon contributions

    c_ij(k) = |x_ik - x_jk| / (sum_k x_ik + sum_k x_jk)

and the operator reports, per taxon, the mean contribution over all
cross-group pairs, the mean abundance in each group, the standard
deviation and ratio of the contributions, and the cumulative
contribution after sorting by decreasing average.

The numbers match ``vegan::simper`` with ``permutations = 0`` for the
``average``, ``ava``, ``avb`` and ``cumsum`` columns.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ecology_common import abundance, group_codes, normalize_group


class SimperStep(Step):
    """SIMPER decomposition of the Bray-Curtis dissimilarity."""

    provider = 'operon-microbiome'
    parameters_file = 'simper.SimperStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'simper',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'SIMPER',
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
                                        {'param': 'group_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'SIMPER decomposition of Bray-Curtis dissimilarity between two groups.'}

    def run(self, ctx: Context, inputs) -> None:
        table_form, meta_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        first_label = normalize_group(ctx.step_params["group_a"])
        second_label = normalize_group(ctx.step_params["group_b"])
        if first_label is None or second_label is None:
            raise StepError("simper: group_a and group_b must be non-empty labels")
        if first_label == second_label:
            raise StepError("simper: group_a and group_b must differ")

        data, samples, taxa = abundance(table_form, sample_dim, taxon_dim, "simper")
        codes = group_codes(meta_form, group_dim, group_label, samples, "simper")
        first = np.flatnonzero(codes == first_label)
        second = np.flatnonzero(codes == second_label)
        if first.size == 0:
            raise StepError(f"simper: group {first_label!r} has no samples")
        if second.size == 0:
            raise StepError(f"simper: group {second_label!r} has no samples")

        totals = data.sum(axis=1)
        denominator = totals[first][:, None] + totals[second][None, :]
        differences = np.abs(data[first][:, None, :] - data[second][None, :, :])
        safe = np.where(denominator > 0.0, denominator, np.inf)
        contributions = (differences / safe[:, :, None]).reshape(-1, data.shape[1])
        average = contributions.mean(axis=0)
        overall = float(average.sum())
        if contributions.shape[0] > 1:
            spread = contributions.std(axis=0, ddof=1)
        else:
            spread = np.full(data.shape[1], np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(spread > 0.0, average / spread, np.nan)
        order = np.argsort(-average, kind="stable")
        if overall > 0.0:
            cumulative = np.cumsum(average[order]) / overall
        else:
            cumulative = np.full(average.shape[0], np.nan)

        names = ["average", "ava", "avb", "sd", "ratio", "cumsum"]
        values = np.column_stack([
            average[order],
            data[first].mean(axis=0)[order],
            data[second].mean(axis=0)[order],
            spread[order],
            ratio[order],
            cumulative,
        ])
        out = Form(
            data=np.asarray(values, dtype=np.float32),
            dims=["taxon", "statistic"],
            labels={
                "taxon": {taxa[index]: position for position, index in enumerate(order)},
                "statistic": {name: position for position, name in enumerate(names)},
            },
            info={
                "missing_code": np.nan,
                "method": "simper",
                "overall": overall,
                "group_a": first_label,
                "group_b": second_label,
                "n_a": int(first.size),
                "n_b": int(second.size),
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "overall": overall,
            "group_a": first_label,
            "group_b": second_label,
            "n_a": int(first.size),
            "n_b": int(second.size),
            "n_taxa": len(taxa),
        }
        print(f"[{self.name}] overall={overall:.6f}")

    def export(self, ctx: Context) -> dict:
        return self._export
