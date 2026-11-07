"""Reverse-complement a DNA/RNA sequence-codes form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences, reverse_complement


class ReverseComplementStep(Step):
    provider = 'operon-core'
    parameters_file = 'reverse_complement.ReverseComplementStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'reverse_complement',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Reverse complement',
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
     'description': 'Reverse complement：接收 1 个输入，输出 Form；主要参数：序列维度、位置维度。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        alphabet = form.info.get("alphabet")
        if alphabet not in ("dna", "rna"):
            raise StepError(f"reverse_complement requires dna/rna, got {alphabet!r}")
        seqs = [reverse_complement(s, alphabet) for s in decode_sequences(form, seq_dim, pos_dim)]
        max_len = max((len(s) for s in seqs), default=0)
        data = np.full((len(seqs), max_len), np.nan, dtype=np.float32)
        amap = dict(form.info.get("alphabet_map", {}))
        unknown = int(form.info.get("unknown_code", 5))
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = amap.get(ch, unknown)
        pos_labels = {str(i): i for i in range(max_len)}
        labels = {seq_dim: dict(form.labels[seq_dim]), pos_dim: pos_labels}
        info = dict(form.info)
        info.update(missing_code=np.nan, representation="sequence_codes", alphabet=alphabet)
        out = Form(data=data, dims=[seq_dim, pos_dim], labels=labels, info=info)
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(seqs), "alphabet": alphabet, "max_position": max_len}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
