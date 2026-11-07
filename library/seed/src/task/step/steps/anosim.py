"""ANOSIM on a symmetric distance matrix."""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import distance, scalar_form
from ._ext_common import group_values


def _statistic(ranks: np.ndarray, codes: np.ndarray) -> float:
    n = len(codes)
    tri = np.triu_indices(n, 1)
    within_mask = codes[tri[0]] == codes[tri[1]]
    if not within_mask.any() or within_mask.all():
        raise StepError("anosim: need at least two groups and within-group pairs")
    within = float(np.mean(ranks[within_mask]))
    between = float(np.mean(ranks[~within_mask]))
    div = n * (n - 1) / 4.0
    return (between - within) / div


class AnosimStep(Step):
    provider = 'operon-microbiome'
    parameters_file = 'anosim.AnosimStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'anosim',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ANOSIM',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
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
     'description': 'ANOSIM：接收 2 个输入，输出 Form；主要参数：样本维度、Sample B Dim、分组维度、分组字段、N Perm、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        dist_form, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        D, samples = distance(dist_form, sample_dim, sample_b_dim, "anosim")
        meta_samples, values = group_values(meta, group_dim, group_label)
        meta_pos = {name: i for i, name in enumerate(meta_samples)}
        keep = [i for i, name in enumerate(samples) if name in meta_pos]
        if len(keep) < 4:
            raise StepError(f"anosim: only {len(keep)} shared samples")
        D = D[np.ix_(keep, keep)]
        codes_raw = [str(values[meta_pos[samples[i]]]) for i in keep]
        groups = sorted(set(codes_raw))
        if len(groups) < 2:
            raise StepError("anosim: need at least two groups")
        codes = np.asarray([groups.index(value) for value in codes_raw], dtype=np.int64)
        if np.bincount(codes).min() < 2:
            raise StepError("anosim: every group needs at least two samples")
        n = len(codes)
        tri = np.triu_indices(n, 1)
        observed = _statistic(rankdata(D[tri], method="average"), codes)
        n_perm = int(ctx.step_params.get("n_perm", 999))
        rng = np.random.default_rng(int(ctx.step_params.get("random_state", 0)))
        permuted = np.empty(n_perm, dtype=np.float64)
        for i in range(n_perm):
            order = rng.permutation(n)
            permuted[i] = _statistic(
                rankdata(D[np.ix_(order, order)][tri], method="average"), codes
            )
        p = (int(np.sum(permuted >= observed)) + 1) / (n_perm + 1)
        form = scalar_form([observed, p, n, len(groups), n_perm],
                           ["R", "p", "n", "n_groups", "n_perm"], "anosim")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"R": float(observed), "p": float(p), "n": n,
                        "n_groups": len(groups), "n_perm": n_perm}
        print(f"[anosim] R={observed:.6g} p={p:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
