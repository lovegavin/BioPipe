"""Synonymous GC harmonisation of coding sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._sequence_common import encode_sequences
from ._codon_design_utils import (
    design_metrics,
    gc_fraction,
    harmonize,
    parse_motifs,
    translate,
)
from .codon_optimize import read_reference_cds_from_sequences


class CodonGcHarmonizeStep(Step):
    provider = "operon-core"
    parameters_file = "codon_gc_harmonize.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "codon_gc_harmonize",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon GC harmonisation",
        "description": "Move coding sequences toward a target GC content with synonymous codon swaps.",
        "category": "Sequence",
        "icon": "Gauge",
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
        return max(3 * size, 16 * 1024 * 1024), 8 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        sequence_dim = params.get("sequence_dim", "sequence")
        position_dim = params.get("position_dim", "position")
        out_name = params.get("output", "codon_gc_harmonize")
        target = float(params.get("target_gc", 0.5))
        if not 0.0 < target < 1.0:
            from src.core.errors import StepError

            raise StepError("codon_gc_harmonize: target_gc must be inside (0, 1)")
        motifs = parse_motifs(params.get("motifs", "GAATTC,GGATCC,AAGCTT,GCGGCCGC"))
        max_run = int(params.get("max_homopolymer", 6))
        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "codon_gc_harmonize")
        _, references = fasta_sequences(inputs[1], sequence_dim, position_dim, "codon_gc_harmonize")
        weights, used_reference = read_reference_cds_from_sequences(references)
        out_names, out_sequences, values = [], [], []
        for name, raw in zip(names, sequences):
            sequence = str(raw).upper().strip()
            if len(sequence) < 3 or len(sequence) % 3 != 0 or any(base not in "ACGT" for base in sequence):
                continue
            protein = translate(sequence)
            if "*" in protein[:-1]:
                continue
            if protein.endswith("*"):
                sequence = sequence[:-3]
            harmonised = harmonize(sequence, weights, target, motifs, max_run)
            if translate(harmonised) != translate(sequence):
                from src.core.errors import StepError

                raise StepError("codon_gc_harmonize: synonymous swap changed the protein")
            out_names.append(name)
            out_sequences.append(harmonised)
            metrics = design_metrics(harmonised, weights, motifs)
            values.append((gc_fraction(sequence), metrics["gc_fraction"], metrics["cai"], metrics["forbidden_sites"]))
        data = np.asarray(values, dtype=np.float64).reshape(len(values), 4)
        out = encode_sequences(
            list(out_sequences),
            sequence_dim,
            position_dim,
            "dna",
            labels={
                sequence_dim: {name: index for index, name in enumerate(out_names)},
                position_dim: {str(i): i for i in range(max((len(s) for s in out_sequences), default=0))},
            },
            info_extra={
                "n_sequences": len(out_sequences),
                "reference_cds": used_reference,
                "target_gc": target,
                "mean_gc_before": float(np.mean(data[:, 0])) if len(values) else float("nan"),
                "mean_gc_after": float(np.mean(data[:, 1])) if len(values) else float("nan"),
                "metrics": {
                    name: {
                        "gc_before": float(row[0]),
                        "gc_after": float(row[1]),
                        "cai": float(row[2]),
                        "forbidden_sites": int(row[3]),
                    }
                    for name, row in zip(out_names, values)
                },
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(out_sequences),
            "mean_gc_before": float(np.mean(data[:, 0])) if len(values) else float("nan"),
            "mean_gc_after": float(np.mean(data[:, 1])) if len(values) else float("nan"),
            "forbidden_sites": int(np.sum(data[:, 3])) if len(values) else 0,
        }

    def export(self, ctx):
        return dict(self._export_data)
