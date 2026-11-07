"""Mantel test between two square distance matrices."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def _aligned(form, dim: str, dim_b: str, name: str):
    if form.data.ndim != 2:
        raise StepError(f"{name}: matrix must be 2D")
    if form.dims != [dim, dim_b]:
        raise StepError(
            f"{name}: matrix must have dims [{dim!r}, {dim_b!r}], got {form.dims}"
        )
    labels = form.labels.get(dim, {})
    if len(labels) != form.data.shape[0] or form.data.shape[0] != form.data.shape[1]:
        raise StepError(f"{name}: matrix must be square with one label per row")
    return form, labels


class MantelStep(Step):
    provider = 'operon-core'
    parameters_file = 'mantel.MantelStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mantel',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Mantel test',
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
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Mantel test：接收 2 个输入，输出 Form；主要参数：样本维度、Sample B Dim、N Perm、随机种子、Alternative。'}

    def run(self, ctx: Context, inputs) -> None:
        dim = ctx.step_params.get("sample_dim", "sample")
        dim_b = ctx.step_params.get("sample_b_dim", "sample_b")
        a, alabels = _aligned(inputs[0], dim, dim_b, "mantel")
        b, blabels = _aligned(inputs[1], dim, dim_b, "mantel")
        common = [name for name in alabels if name in blabels]
        if len(common) < 3:
            raise StepError(f"mantel: need at least 3 shared samples, got {len(common)}")
        ai = [alabels[name] for name in common]
        bi = [blabels[name] for name in common]
        a_data = np.asarray(a.data, dtype=np.float64)[np.ix_(ai, ai)]
        b_data = np.asarray(b.data, dtype=np.float64)[np.ix_(bi, bi)]
        if not (np.isfinite(a_data).all() and np.isfinite(b_data).all()):
            raise StepError("mantel: distance matrices must be finite")
        if not np.allclose(a_data, a_data.T) or not np.allclose(b_data, b_data.T):
            raise StepError("mantel: distance matrices must be symmetric")
        tri = np.triu_indices(len(common), 1)
        x = a_data[tri]
        y = b_data[tri]
        if np.std(x) == 0 or np.std(y) == 0:
            raise StepError("mantel: a distance matrix has zero variance")
        observed = float(np.corrcoef(x, y)[0, 1])
        n_perm = int(ctx.step_params.get("n_perm", 999))
        rng = np.random.default_rng(int(ctx.step_params.get("random_state", 0)))
        permuted = np.empty(n_perm, dtype=np.float64)
        for i in range(n_perm):
            order = rng.permutation(len(common))
            permuted[i] = float(np.corrcoef(x, b_data[np.ix_(order, order)][tri])[0, 1])
        alt = ctx.step_params.get("alternative", "greater")
        if alt == "greater":
            p = (int(np.sum(permuted >= observed)) + 1) / (n_perm + 1)
        elif alt == "less":
            p = (int(np.sum(permuted <= observed)) + 1) / (n_perm + 1)
        else:
            p = 2.0 * min(
                (int(np.sum(permuted >= observed)) + 1) / (n_perm + 1),
                (int(np.sum(permuted <= observed)) + 1) / (n_perm + 1),
            )
        z = float(np.sum(x * y) / len(x))
        out = np.array([[observed], [p], [z], [float(len(common))]], dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=out, dims=["statistic", "value"],
            labels={"statistic": {"r": 0, "p": 1, "z": 2, "n": 3}, "value": {"value": 0}},
            info={"method": "mantel_pearson", "n_perm": n_perm, "alternative": alt},
        )
        self._export = {"n_samples": len(common), "r": observed, "p": float(p), "n_perm": n_perm}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
