"""Weighted Cohen kappa for two numeric raters."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import reorder, require_dims
from ._stats20_common import scalar_form


class WeightedKappaStep(Step):
    provider = 'operon-core'
    parameters_file = 'weighted_kappa.WeightedKappaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'weighted_kappa',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Weighted kappa',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{'version': 1, 'numeric': True, 'info': {},
                        'dims': [{'param': 'subject_dim', 'default': 'subject'},
                                 {'param': 'rater_dim', 'default': 'rater'}],
                        'labels': [], 'parallel': [], 'ndim': 2}],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
        'dependency_imports': ['numpy', 'scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': "Weighted Cohen's kappa for two raters with linear or "
                       "quadratic disagreement weights.",
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        subject_dim = ctx.step_params.get("subject_dim", "subject")
        rater_dim = ctx.step_params.get("rater_dim", "rater")
        weighting = ctx.step_params.get("weights", "linear")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, subject_dim, rater_dim, label="weighted_kappa")
        if weighting not in ("linear", "quadratic"):
            raise StepError("weighted_kappa: weights must be 'linear' or 'quadratic'")
        data = reorder(form, subject_dim, rater_dim)
        if data.shape[1] != 2:
            raise StepError(
                f"weighted_kappa: expected exactly two raters, got {data.shape[1]}")
        data = data[np.isfinite(data).all(axis=1)]
        if data.shape[0] < 2:
            raise StepError("weighted_kappa: need at least two rated subjects")
        levels = np.unique(data)
        if levels.size < 2:
            raise StepError("weighted_kappa: need at least two rating categories")
        codes = np.searchsorted(levels, data)
        ncat = levels.size
        table = np.zeros((ncat, ncat), dtype=np.float64)
        for a, b in codes:
            table[a, b] += 1.0
        n = table.sum()
        rows = table.sum(axis=1)
        cols = table.sum(axis=0)
        index = np.arange(ncat)
        gap = np.abs(index[:, None] - index[None, :])
        if weighting == "linear":
            weights = 1.0 - gap / (ncat - 1)
        else:
            weights = 1.0 - gap ** 2 / (ncat - 1) ** 2
        agree = float(np.sum(table * weights)) / n
        expected = np.outer(rows, cols) / n
        chance = float(np.sum(expected * weights)) / n
        if chance >= 1.0:
            raise StepError("weighted_kappa: chance agreement is 1")
        kappa = (agree - chance) / (1.0 - chance)
        w_i = (weights * (cols / n)[None, :]).sum(axis=1)
        w_j = (weights * (rows / n)[:, None]).sum(axis=0)
        variance_matrix = (expected / n) * (weights - (w_i[:, None] + w_j[None, :])) ** 2
        variance = (variance_matrix.sum() - chance ** 2) / (n * (1.0 - chance) ** 2)
        se = float(np.sqrt(max(variance, 0.0)))
        if se == 0.0:
            raise StepError("weighted_kappa: standard error is zero")
        z = kappa / se
        p = float(2.0 * stats.norm.sf(abs(z)))
        names = ["kappa", "se", "z", "p_value", "n_subjects", "n_categories"]
        values = [kappa, se, z, p, n, ncat]
        ctx[out_name] = scalar_form(values, names, "weighted_kappa")
        self._export = {"kappa": float(kappa), "se": se, "z": float(z), "p": p,
                        "weights": weighting, "n_categories": int(ncat)}
        print(f"[weighted_kappa] kappa={kappa:.6g} p={p:.6g} weights={weighting}")

    def export(self, ctx: Context) -> dict:
        return self._export
