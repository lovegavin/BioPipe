"""Translate DNA/RNA sequences to protein sequence codes."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import PROTEIN_MAP, decode_sequences, translate_sequence


class TranslateStep(Step):
    provider = 'operon-core'
    parameters_file = 'translate.TranslateStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'translate',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Translate sequences',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'enum': ['dna', 'rna']},
                                        'missing_code': {'type': ['number', 'null']}},
                               'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                                        {'param': 'position_dim', 'default': 'position'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Translate sequences：接收 1 个输入，输出 Form；主要参数：序列维度、位置维度、Frame、To Stop。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        frame = int(ctx.step_params.get("frame", 0))
        to_stop = bool(ctx.step_params.get("to_stop", True))
        out_name = ctx.step_params.get("output", self.name)
        proteins = [translate_sequence(s, frame, to_stop) for s in decode_sequences(form, seq_dim, pos_dim)]
        max_len = max((len(p) for p in proteins), default=0)
        data = np.full((len(proteins), max_len), np.nan, dtype=np.float32)
        for i, protein in enumerate(proteins):
            for j, aa in enumerate(protein):
                data[i, j] = PROTEIN_MAP.get(aa, len(PROTEIN_MAP))
        labels = {
            seq_dim: dict(form.labels[seq_dim]),
            pos_dim: {str(i): i for i in range(max_len)},
        }
        info = {
            "missing_code": np.nan,
            "representation": "sequence_codes",
            "alphabet": "protein",
            "alphabet_map": dict(PROTEIN_MAP),
            "unknown_code": len(PROTEIN_MAP),
            "translation_frame": frame,
            "translated_to_stop": to_stop,
        }
        out = Form(data=data, dims=[seq_dim, pos_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(proteins), "frame": frame, "to_stop": to_stop,
                             "max_protein_length": max_len, "alphabet": "protein"}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
