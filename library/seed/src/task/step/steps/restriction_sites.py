"""Count restriction-enzyme recognition sites in DNA sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import count_motif, decode_sequences, reverse_complement

_DEFAULT_ENZYMES = {
    "EcoRI": "GAATTC", "BamHI": "GGATCC", "HindIII": "AAGCTT",
    "NotI": "GCGGCCGC", "XhoI": "CTCGAG", "PstI": "CTGCAG",
    "SalI": "GTCGAC", "KpnI": "GGTACC", "SacI": "GAGCTC",
    "SmaI": "CCCGGG", "TaqI": "TCGA", "AluI": "AGCT",
}


class RestrictionSitesStep(Step):
    provider = 'operon-core'
    parameters_file = 'restriction_sites.RestrictionSitesStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'restriction_sites',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Restriction sites',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'enum': ['dna']},
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
     'description': 'Restriction sites：接收 1 个输入，输出 Form；主要参数：序列维度、位置维度、Enzymes。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        out_name = ctx.step_params.get("output", self.name)
        enzymes = ctx.step_params.get("enzymes") or dict(_DEFAULT_ENZYMES)
        if not isinstance(enzymes, dict) or not enzymes:
            raise StepError("enzymes must be a non-empty mapping name -> motif")
        for name, motif in enzymes.items():
            if not isinstance(motif, str) or not motif or set(motif.upper()) - set("ACGTN"):
                raise StepError(f"invalid motif for {name!r}: {motif!r}")
        seqs = decode_sequences(form, seq_dim, pos_dim)
        names = list(enzymes)
        data = np.zeros((len(seqs), len(names)), dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, name in enumerate(names):
                motif = enzymes[name].upper()
                rev = reverse_complement(motif, "dna")
                count = count_motif(seq, motif)
                if rev != motif:
                    count += count_motif(seq, rev)
                data[i, j] = count
        out = Form(
            data=data,
            dims=[seq_dim, "enzyme"],
            labels={seq_dim: dict(form.labels[seq_dim]), "enzyme": {name: i for i, name in enumerate(names)}},
            info={"missing_code": np.nan},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_sequences": len(seqs), "enzymes": names, "counts": data.tolist()}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
