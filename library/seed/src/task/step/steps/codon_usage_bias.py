"""Effective number of codons and GC3s per CDS."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.core.errors import StepError
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._codon_bias_utils import clean_cds, codon_counts, enc_wright, gc3s_variants


class CodonUsageBiasStep(Step):
    provider = "operon-core"
    parameters_file = "codon_usage_bias.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "codon_usage_bias",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon usage bias",
        "description": "Effective number of codons (Wright) and GC3s for each coding sequence.",
        "category": "Omics",
        "icon": "ChartBar",
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
        return max(size, 16 * 1024 * 1024), 4 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        sequence_dim = params.get("sequence_dim", "sequence")
        position_dim = params.get("position_dim", "position")
        out_name = params.get("output", "codon_usage_bias")
        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "codon_usage_bias")
        rows = []
        for raw in sequences:
            sequence = clean_cds(raw, "codon_usage_bias")
            counts = codon_counts(sequence)
            enc_value = enc_wright(sequence)
            gc3 = gc3s_variants(sequence)["multi"]
            rows.append((enc_value, gc3, float(sum(counts.values()))))
        if not rows:
            raise StepError("codon_usage_bias: no coding sequences were provided")
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data,
            dims=[sequence_dim, "statistic"],
            labels={sequence_dim: {name: index for index, name in enumerate(names)},
                    "statistic": {"enc": 0, "gc3s": 1, "codons": 2}},
            info={"n_sequences": len(names),
                  "mean_enc": float(np.mean(data[:, 0])),
                  "mean_gc3s": float(np.mean(data[:, 1]))},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(names),
            "mean_enc": float(np.mean(data[:, 0])),
            "mean_gc3s": float(np.mean(data[:, 1])),
        }

    def export(self, ctx):
        return dict(self._export_data)
