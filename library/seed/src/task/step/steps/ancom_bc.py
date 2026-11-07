# src/task/step/steps/ancom_bc.py
"""Log-ratio differential abundance with sample-bias removal.

This implements the core contrast used by ANCOM-BC-style analyses:
log-counts are centred per sample (removing sample-specific bias),
the group contrast is estimated, and a Welch test plus BH correction
is reported. It is an independent Python implementation, not a direct
R ANCOMBC wrapper; structural-zero estimation and the full ANCOM-BC
mixed model are intentionally not claimed.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._da_common import ancom_style, prepare
from ._ext_common import axis_labels, correct, make_form

_COLUMNS = ["logFC", "effect", "P_VALUE", "Q_VALUE", "n_a", "n_b"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


class AncomBcStep(Step):
    provider = 'operon-microbiome'
    parameters_file = 'ancom_bc.AncomBcStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ancom_bc',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Log-ratio differential abundance',
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
                               'dims': [{'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2,
                               'labels_any': [{'param': 'group_label', 'default': None}]}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Log-ratio differential abundance：接收 2 个输入，输出 Form；主要参数：样本维度、Taxon Dim、分组字段、A 组、B '
                    '组、伪计数。'}

    def run(self, ctx: Context, inputs) -> None:
        table, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        pseudocount = float(ctx.step_params.get("pseudocount", 1.0))
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        if pseudocount <= 0:
            raise StepError("ancom_bc: pseudocount must be > 0")
        if correction not in _CORRECTIONS:
            raise StepError(f"ancom_bc: unknown correction {correction!r}")
        data, a, b, taxa = prepare(table, meta, sample_dim, taxon_dim, group_label, group_a, group_b)
        diff, effect, p, n_a, n_b = ancom_style(data, a, b, pseudocount=pseudocount)
        q = correct(p, correction)
        out = np.column_stack([diff, effect, p, q,
                               np.full(len(taxa), n_a), np.full(len(taxa), n_b)])
        form = make_form(
            out, [taxon_dim, "statistic"],
            {taxon_dim: axis_labels(taxa, taxon_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "n_a": n_a, "n_b": n_b,
            "pseudocount": pseudocount, "significant": int((q < 0.05).sum()),
            "results": [
                {"taxon": taxa[i], "logFC": float(diff[i]), "effect": float(effect[i]),
                 "P_VALUE": float(p[i]), "Q_VALUE": float(q[i])}
                for i in range(len(taxa))
            ],
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_a": n_a, "n_b": n_b, "significant": int((q < 0.05).sum()),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
