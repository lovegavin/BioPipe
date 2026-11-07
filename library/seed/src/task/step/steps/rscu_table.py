"""Aggregate relative synonymous codon usage (RSCU) table."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.core.errors import StepError
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._codon_bias_utils import AA_CODON_ORDER, clean_cds, codon_counts, rscu


class RscuTableStep(Step):
    provider = "operon-core"
    parameters_file = "rscu_table.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rscu_table",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Relative synonymous codon usage",
        "description": "Aggregate codon counts and RSCU across a coding sequence set.",
        "category": "Omics",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(2 * size, 16 * 1024 * 1024), 4 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        sequence_dim = params.get("sequence_dim", "sequence")
        position_dim = params.get("position_dim", "position")
        out_name = params.get("output", "rscu")
        _, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "rscu_table")
        counts = {}
        for raw in sequences:
            sequence = clean_cds(raw, "rscu_table")
            for codon, value in codon_counts(sequence).items():
                counts[codon] = counts.get(codon, 0) + value
        total = sum(counts.values())
        if total == 0:
            raise StepError("rscu_table: no codons were counted")
        values = rscu(counts)
        codons = [codon for aa in AA_CODON_ORDER for codon in AA_CODON_ORDER[aa]]
        data = np.asarray([[float(counts.get(codon, 0)), counts.get(codon, 0) / total, values[codon]]
                           for codon in codons], dtype=np.float64)
        out = Form(
            data,
            dims=["codon", "statistic"],
            labels={"codon": {codon: index for index, codon in enumerate(codons)},
                    "statistic": {"count": 0, "fraction": 1, "rscu": 2}},
            info={"total_codons": int(total), "n_codons": len(codons),
                  "n_sequences": len(sequences)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"total_codons": int(total), "n_codons": len(codons)}

    def export(self, ctx):
        return dict(self._export_data)
