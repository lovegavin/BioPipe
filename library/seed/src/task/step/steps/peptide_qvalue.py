"""Target-decoy q-values for peptide-spectrum matches."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form


class PeptideQvalueStep(Step):
    provider = 'operon-core'
    parameters_file = 'peptide_qvalue.PeptideQvalueStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'peptide_qvalue',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Peptide q-values',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'psm_dim', 'default': 'psm'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Peptide q-values：接收 1 个输入，输出 Form；主要参数：Psm Dim、特征维度、Score Label、Decoy Label、Decoy '
                    'Values。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        psm_dim = ctx.step_params.get("psm_dim", "psm")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        score_label = ctx.step_params["score_label"]
        decoy_label = ctx.step_params["decoy_label"]
        decoy_values = {str(v) for v in ctx.step_params.get("decoy_values", [1])}
        out_name = ctx.step_params.get("output", self.name)
        if score_label not in form.labels.get(feature_dim, {}):
            raise StepError(f"score column {score_label!r} not found")
        if decoy_label not in form.labels.get(feature_dim, {}):
            raise StepError(f"decoy column {decoy_label!r} not found")
        data = np.asarray(form.data, dtype=np.float64)
        axis = form.dims.index(psm_dim)
        data = np.moveaxis(data, axis, 0)
        scores = data[:, form.labels[feature_dim][score_label]]
        decoy_raw = data[:, form.labels[feature_dim][decoy_label]]
        decoy = np.array([str(v) in decoy_values for v in decoy_raw])
        finite = np.isfinite(scores)
        order = np.argsort(-scores[finite], kind="mergesort")
        idx = np.where(finite)[0][order]
        q = np.ones(len(idx), dtype=np.float64)
        n_decoy = 0; n_target = 0
        for pos, i in enumerate(idx):
            if decoy[i]:
                n_decoy += 1
            else:
                n_target += 1
            q[pos] = (n_decoy + 1) / max(n_target, 1)
        for pos in range(len(q) - 2, -1, -1):
            q[pos] = min(q[pos], q[pos + 1])
        out_q = np.full(len(scores), np.nan, dtype=np.float64)
        out_q[idx] = np.minimum(q, 1.0)
        psm_names = labels_in_order(form, psm_dim)
        out = make_form(np.column_stack([out_q, scores, decoy.astype(float)]), [psm_dim, "statistic"],
                        {psm_dim: {name: i for i, name in enumerate(psm_names)},
                         "statistic": {"qvalue": 0, "score": 1, "decoy": 2}})
        ctx[out_name] = out
        self._export_data = {"n_psms": len(scores), "n_targets": n_target, "n_decoys": n_decoy,
                             "n_q_lt_0_01": int(np.sum(out_q < 0.01))}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
