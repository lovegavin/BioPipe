"""Partial Mantel correlation of two distance matrices controlling a third."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import distance, scalar_form


def _residual(values: np.ndarray, control: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(values)), control])
    beta, *_ = np.linalg.lstsq(design, values, rcond=None)
    return values - design @ beta


class PartialMantelStep(Step):
    provider = 'operon-core'
    parameters_file = 'partial_mantel.PartialMantelStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'partial_mantel',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Partial Mantel test',
     'category': 'Statistics',
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
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
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
     'inputs_arity': 3,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Partial Mantel test：接收 3 个输入，输出 Form；主要参数：样本维度、Sample B Dim、N Perm、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        dim = ctx.step_params.get("sample_dim", "sample")
        dim_b = ctx.step_params.get("sample_b_dim", "sample_b")
        A, a_labels = distance(inputs[0], dim, dim_b, "partial_mantel A")
        B, b_labels = distance(inputs[1], dim, dim_b, "partial_mantel B")
        C, c_labels = distance(inputs[2], dim, dim_b, "partial_mantel C")
        common = [name for name in a_labels if name in b_labels and name in c_labels]
        if len(common) < 4:
            raise StepError(f"partial_mantel: only {len(common)} shared samples")
        a_pos = {name: i for i, name in enumerate(a_labels)}
        b_pos = {name: i for i, name in enumerate(b_labels)}
        c_pos = {name: i for i, name in enumerate(c_labels)}
        ai = [a_pos[name] for name in common]
        bi = [b_pos[name] for name in common]
        ci = [c_pos[name] for name in common]
        A = A[np.ix_(ai, ai)]
        B = B[np.ix_(bi, bi)]
        C = C[np.ix_(ci, ci)]
        tri = np.triu_indices(len(common), 1)
        a = A[tri]
        b = B[tri]
        c = C[tri]
        if np.std(a) == 0 or np.std(b) == 0 or np.std(c) == 0:
            raise StepError("partial_mantel: a distance matrix has zero variance")
        ra = _residual(a, c)
        rb = _residual(b, c)
        observed = float(np.corrcoef(ra, rb)[0, 1])
        n_perm = int(ctx.step_params.get("n_perm", 999))
        rng = np.random.default_rng(int(ctx.step_params.get("random_state", 0)))
        permuted = np.empty(n_perm, dtype=np.float64)
        for i in range(n_perm):
            order = rng.permutation(len(common))
            Bp = B[np.ix_(order, order)]
            bp = Bp[tri]
            rbp = _residual(bp, c)
            permuted[i] = float(np.corrcoef(ra, rbp)[0, 1])
        p = (int(np.sum(permuted >= observed)) + 1) / (n_perm + 1)
        form = scalar_form([observed, p, len(common), n_perm],
                           ["r", "p", "n", "n_perm"], "partial_mantel")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"r": observed, "p": float(p), "n": len(common), "n_perm": n_perm}
        print(f"[partial_mantel] r={observed:.6g} p={p:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
