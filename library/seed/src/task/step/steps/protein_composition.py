"""Amino-acid composition of protein sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._protein_qc_utils import AA20, composition, prepare_sequences


class ProteinCompositionStep(Step):
    provider = 'operon-core'
    parameters_file = 'protein_composition.ProteinCompositionStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'protein_composition',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Protein amino-acid composition',
        'category': 'Proteomics',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                         'alphabet': {'type': 'string', 'const': 'protein'},
                         'missing_code': {'type': ['number', 'null']}},
                'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                         {'param': 'position_dim', 'default': 'position'}],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True, 'info_open': False,
                                  'axis_info_open': False,
                                  'info': {'missing_code': {'type': ['number', 'null']}}}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Counts the 20 standard amino acids for every protein sequence.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        seq_dim = ctx.step_params.get("sequence_dim", "sequence")
        pos_dim = ctx.step_params.get("position_dim", "position")
        residue_dim = ctx.step_params.get("residue_dim", "residue")
        out_name = ctx.step_params.get("output", self.name)
        names, sequences, skipped = prepare_sequences(
            form, seq_dim, pos_dim, "protein_composition")
        rows = [composition(seq) for seq in sequences]
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, residue_dim],
            labels={seq_dim: {name: index for index, name in enumerate(names)}, residue_dim: {aa: i for i, aa in enumerate(AA20)}},
            info={"missing_code": np.nan, "skipped_unsupported": skipped},
        )
        out.validate()
        ctx[out_name] = out
        total = int(data.sum())
        self._export_data = {
            "n_proteins": len(sequences),
            "skipped_unsupported": skipped,
            "residues": list(AA20),
            "total_residues": total,
            "mean_length": (total / len(sequences)) if sequences else 0.0,
        }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (4 * 1024 * 1024, 1024 * 1024)

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
