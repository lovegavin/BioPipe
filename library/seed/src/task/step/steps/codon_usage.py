"""Codon counts and frequencies from CDS sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import CODON_TABLE, decode_sequences


class CodonUsageStep(Step):
    provider = 'operon-core'
    parameters_file = 'codon_usage.CodonUsageStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'codon_usage',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Codon usage',
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
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Codon usage：接收 1 个输入，输出 Form；主要参数：序列维度、位置维度、Frame。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        frame = int(ctx.step_params.get("frame", 0))
        out_name = ctx.step_params.get("output", self.name)
        codons = sorted(CODON_TABLE)
        counts = {c: 0 for c in codons}
        for seq in decode_sequences(form, seq_dim, pos_dim):
            seq = seq.upper().replace("U", "T")
            for i in range(frame, len(seq) - 2, 3):
                codon = seq[i:i + 3]
                if codon in counts:
                    counts[codon] += 1
        total = sum(counts.values())
        data = np.array([[counts[c], (counts[c] / total if total else 0.0)] for c in codons], dtype=np.float32)
        out = Form(
            data=data,
            dims=["codon", "statistic"],
            labels={"codon": {c: i for i, c in enumerate(codons)},
                    "statistic": {"count": 0, "frequency": 1}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_codons": total, "frame": frame, "n_codons_types": len(codons)}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
