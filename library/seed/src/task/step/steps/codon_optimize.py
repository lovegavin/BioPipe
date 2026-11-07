"""Codon optimisation of protein sequences using a reference CDS set."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._sequence_common import encode_sequences
from ._codon_design_utils import (
    clean_protein,
    design_metrics,
    optimize,
    parse_motifs,
    read_reference_cds,
)


class CodonOptimizeStep(Step):
    provider = "operon-core"
    parameters_file = "codon_optimize.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "codon_optimize",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon optimisation",
        "description": "Reverse-translate proteins with reference codon usage while avoiding motifs and homopolymers.",
        "category": "Sequence",
        "icon": "Dna",
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
        out_name = params.get("output", "codon_optimize")
        motifs = parse_motifs(params.get("motifs", "GAATTC,GGATCC,AAGCTT,GCGGCCGC,TCTAGA,GTCGAC,CTGCAG"))
        gc_min = float(params.get("gc_min", 0.4))
        gc_max = float(params.get("gc_max", 0.6))
        max_run = int(params.get("max_homopolymer", 6))
        max_sequences = int(params.get("max_sequences", 0))
        if not 0.0 <= gc_min < gc_max <= 1.0:
            from src.core.errors import StepError

            raise StepError("codon_optimize: gc_min must be below gc_max and inside [0, 1]")
        names, proteins = fasta_sequences(inputs[0], sequence_dim, position_dim, "codon_optimize")
        _, references = fasta_sequences(inputs[1], sequence_dim, position_dim, "codon_optimize")
        weights, used_reference = read_reference_cds_from_sequences(references)
        out_names, sequences, values = [], [], []
        for name, protein in zip(names, proteins):
            if max_sequences and len(out_names) >= max_sequences:
                break
            sequence = optimize(str(protein), weights, motifs, (gc_min, gc_max), max_run)
            metrics = design_metrics(sequence, weights, motifs)
            out_names.append(name)
            sequences.append(sequence)
            values.append((metrics["cai"], metrics["gc_fraction"], metrics["forbidden_sites"]))
        data = np.asarray(values, dtype=np.float64).reshape(len(values), 3)
        out = encode_sequences(
            list(sequences),
            sequence_dim,
            position_dim,
            "dna",
            labels={
                sequence_dim: {name: index for index, name in enumerate(out_names)},
                position_dim: {str(i): i for i in range(max((len(s) for s in sequences), default=0))},
            },
            info_extra={
                "n_sequences": len(sequences),
                "reference_cds": used_reference,
                "mean_cai": float(np.mean(data[:, 0])) if len(values) else float("nan"),
                "gc_min": gc_min,
                "gc_max": gc_max,
                "motifs": motifs,
                "metrics": {
                    name: {"cai": float(row[0]), "gc_fraction": float(row[1]), "forbidden_sites": int(row[2])}
                    for name, row in zip(out_names, values)
                },
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(sequences),
            "mean_cai": float(np.mean(data[:, 0])) if len(values) else float("nan"),
            "mean_gc": float(np.mean(data[:, 1])) if len(values) else float("nan"),
            "forbidden_sites": int(np.sum(data[:, 2])) if len(values) else 0,
        }

    def export(self, ctx):
        return dict(self._export_data)


def read_reference_cds_from_sequences(references):
    from ._codon_design_utils import AA_CODONS, CODON_TABLE, translate

    counts = {amino_acid: {codon: 0 for codon in codons} for amino_acid, codons in AA_CODONS.items()}
    used = 0
    for raw in references:
        sequence = str(raw).upper()
        if len(sequence) < 30 or len(sequence) % 3 != 0 or any(base not in "ACGT" for base in sequence):
            continue
        protein = translate(sequence)
        if "*" in protein[:-1]:
            continue
        if protein.endswith("*"):
            protein = protein[:-1]
        if len(protein) < 10:
            continue
        for offset, amino_acid in enumerate(protein):
            codon = sequence[offset * 3:offset * 3 + 3]
            if codon in counts.get(amino_acid, {}):
                counts[amino_acid][codon] += 1
        used += 1
    if used < 5:
        from src.core.errors import StepError

        raise StepError("codon_optimize: reference set yielded fewer than 5 usable CDS sequences")
    weights = {}
    for table in counts.values():
        maximum = max(table.values()) if table else 0
        for codon, count in table.items():
            weights[codon] = max(count / maximum, 1e-6) if maximum else 0.5
    return weights, used
