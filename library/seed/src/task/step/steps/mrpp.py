"""MRPP: multi-response permutation procedure.

Chance-corrected within-group agreement for community data

    delta   = sum_g n_g * delta_g / n        (weight.type = 1)
    E.delta = mean of all pairwise distances
    A       = 1 - delta / E.delta

with ``delta_g`` the mean within-group distance and ``n_g`` the group
size. The p-value is the fraction of label permutations whose ``delta``
is at most the observed value, matching ``vegan::mrpp`` including its
add-one correction.

Supported distances: euclidean, bray (Bray-Curtis) and manhattan.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ecology_common import abundance, group_codes, pairwise


def _within_mean(distances: np.ndarray, indices: np.ndarray) -> float:
    if indices.size < 2:
        return float("nan")
    block = distances[np.ix_(indices, indices)]
    upper = np.triu_indices(indices.size, 1)
    return float(np.mean(block[upper]))


def _delta(distances: np.ndarray, codes: np.ndarray) -> float:
    total = 0.0
    groups = []
    for label in dict.fromkeys(codes):
        index = np.flatnonzero(codes == label)
        if index.size < 2:
            raise StepError(f"mrpp: group {label!r} has fewer than two samples")
        groups.append(index)
    for index in groups:
        total += index.size * _within_mean(distances, index)
    return total / distances.shape[0]


class MrppStep(Step):
    """Multi-response permutation procedure with chance correction."""

    provider = 'operon-microbiome'
    parameters_file = 'mrpp.MrppStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mrpp',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'MRPP',
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
     'description': 'MRPP chance-corrected within-group agreement with a permutation p-value.'}

    def run(self, ctx: Context, inputs) -> None:
        table_form, meta_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        method = str(ctx.step_params.get("distance", "euclidean"))
        n_perm = int(ctx.step_params.get("n_perm", 999))
        random_state = int(ctx.step_params.get("random_state", 0))
        if n_perm < 0:
            raise StepError("mrpp: n_perm must be zero or positive")

        data, samples, _taxa = abundance(table_form, sample_dim, taxon_dim, "mrpp")
        codes = group_codes(meta_form, group_dim, group_label, samples, "mrpp")
        if np.unique(codes).size < 2:
            raise StepError("mrpp: need samples from at least two groups")
        distances = pairwise(data, method, "mrpp")

        for label in dict.fromkeys(codes):
            if np.count_nonzero(codes == label) < 2:
                raise StepError(f"mrpp: group {label!r} has fewer than two samples")

        delta = _delta(distances, codes)
        expected = float(np.mean(distances[np.triu_indices(distances.shape[0], 1)]))
        if expected <= 0.0:
            raise StepError("mrpp: expected delta is zero; distances cannot be normalized")
        chance = 1.0 - delta / expected

        if n_perm > 0:
            rng = np.random.default_rng(random_state)
            tolerance = 1e-12
            extreme = 0
            for _ in range(n_perm):
                shuffled = rng.permutation(codes)
                if _delta(distances, shuffled) <= delta + tolerance:
                    extreme += 1
            p_value = (extreme + 1.0) / (n_perm + 1.0)
        else:
            p_value = float("nan")

        sizes = {
            str(label): int(np.count_nonzero(codes == label))
            for label in dict.fromkeys(codes)
        }

        values = np.asarray([delta, expected, chance, p_value,
                             np.unique(codes).size, codes.size], dtype=np.float64)
        out = Form(
            data=values.astype(np.float32).reshape(-1, 1),
            dims=["statistic", "value"],
            labels={
                "statistic": {
                    name: position
                    for position, name in enumerate(
                        ["delta", "E_delta", "A", "p", "n_groups", "n_samples"]
                    )
                },
                "value": {"value": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "mrpp",
                "distance": method,
                "n_perm": n_perm,
                "random_state": random_state,
                "groups": sorted(sizes),
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "delta": delta,
            "E_delta": expected,
            "A": chance,
            "p": p_value,
            "n_groups": int(np.unique(codes).size),
            "n_samples": int(codes.size),
            "group_sizes": sizes,
        }
        print(f"[{self.name}] delta={delta:.6f} A={chance:.6f} p={p_value:.6f}")

    def export(self, ctx: Context) -> dict:
        return self._export
