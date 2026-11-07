"""Quality control metrics for designed coding sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._codon_design_utils import design_metrics, parse_motifs
from .codon_optimize import read_reference_cds_from_sequences


class CodonDesignQcStep(Step):
    provider = "operon-core"
    parameters_file = "codon_design_qc.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "codon_design_qc",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon design QC",
        "description": "Report CAI, GC content, homopolymers and forbidden sites for designed CDS sequences.",
        "category": "Sequence",
        "icon": "ClipboardCheck",
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
                },
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
                },
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(2 * size, 8 * 1024 * 1024), 4 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        sequence_dim = params.get("sequence_dim", "sequence")
        position_dim = params.get("position_dim", "position")
        out_name = params.get("output", "codon_design_qc")
        motifs = parse_motifs(params.get("motifs", "GAATTC,GGATCC,AAGCTT,GCGGCCGC"))
        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "codon_design_qc")
        _, references = fasta_sequences(inputs[1], sequence_dim, position_dim, "codon_design_qc")
        weights, used_reference = read_reference_cds_from_sequences(references)
        out_names, values = [], []
        for name, raw in zip(names, sequences):
            sequence = str(raw).upper().strip()
            if not sequence:
                continue
            metrics = design_metrics(sequence, weights, motifs)
            out_names.append(name)
            values.append((
                metrics["cai"],
                metrics["gc_fraction"],
                metrics["max_homopolymer"],
                metrics["forbidden_sites"],
                metrics["length_bp"],
            ))
        data = np.asarray(values, dtype=np.float64).reshape(len(values), 5)
        out = Form(
            data,
            dims=[sequence_dim, "statistic"],
            labels={
                sequence_dim: {name: index for index, name in enumerate(out_names)},
                "statistic": {
                    "cai": 0,
                    "gc_fraction": 1,
                    "max_homopolymer": 2,
                    "forbidden_sites": 3,
                    "length_bp": 4,
                },
            },
            info={
                "n_sequences": len(out_names),
                "reference_cds": used_reference,
                "mean_cai": float(np.mean(data[:, 0])) if len(values) else float("nan"),
                "n_forbidden": int(np.sum(data[:, 3])) if len(values) else 0,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(out_names),
            "mean_cai": float(np.mean(data[:, 0])) if len(values) else float("nan"),
            "n_forbidden": int(np.sum(data[:, 3])) if len(values) else 0,
        }

    def export(self, ctx):
        return dict(self._export_data)
