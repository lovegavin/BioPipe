"""In-silico enzymatic digestion of a protein FASTA file."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._annotation_utils import fasta_sequences
from ._proteomics_utils import digest_peptides, peptide_mass

_FIELDS = [
    "protein_index",
    "start",
    "end",
    "length",
    "missed_cleavages",
    "mass",
]


class ProteinDigestStep(Step):
    """Digest proteins with trypsin/Lys-C/Arg-C and report peptide masses."""

    provider = "operon-core"
    parameters_file = "protein_digest.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "protein_digest",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Protein digest",
        "description": (
            "Digest a protein FASTA with a site-specific protease using the "
            "standard cleavage rule (K/R unless followed by P) and report "
            "peptide coordinates, missed cleavages and monoisotopic masses."
        ),
        "category": "Proteomics",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "encoders": {"type": "object", "optional": True},
                    },
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
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes)
        return max(size * 8, 64 * 2**20), 16 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        fasta = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        enzyme = str(params.get("enzyme", "trypsin"))
        missed = int(params.get("missed_cleavages", 0))
        min_length = int(params.get("min_length", 6))
        max_length = int(params.get("max_length", 50))
        out_name = str(params.get("output", self.name))
        if missed < 0 or missed > 3:
            raise StepError("protein_digest: missed_cleavages must be between 0 and 3")
        if min_length < 1:
            raise StepError("protein_digest: min_length must be >= 1")
        if max_length and max_length < min_length:
            raise StepError("protein_digest: max_length must be >= min_length")

        names, sequences = fasta_sequences(
            fasta, sequence_dim, position_dim, "protein_digest"
        )
        proteins = []
        peptide_sequences = []
        labels = []
        rows = []
        skipped = 0
        for protein_index, (name, raw) in enumerate(zip(names, sequences)):
            sequence = str(raw).upper().replace("*", "")
            proteins.append(name)
            if not sequence:
                continue
            for start, end, extra in digest_peptides(sequence, enzyme, missed):
                length = end - start
                if length < min_length:
                    continue
                if max_length and length > max_length:
                    continue
                peptide = sequence[start:end]
                try:
                    mass = peptide_mass(peptide, name, start + 1)
                except StepError:
                    skipped += 1
                    continue
                labels.append(f"{name}:{start + 1}-{end}")
                peptide_sequences.append(peptide)
                rows.append(
                    [
                        float(protein_index),
                        float(start + 1),
                        float(end),
                        float(length),
                        float(extra),
                        float(mass),
                    ]
                )
        if not rows:
            raise StepError("protein_digest: no peptides passed the size filters")

        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data=data,
            dims=["peptide", "field"],
            labels={
                "peptide": {label: index for index, label in enumerate(labels)},
                "field": {field: index for index, field in enumerate(_FIELDS)},
            },
            info={
                "enzyme": enzyme,
                "missed_cleavages": missed,
                "min_length": min_length,
                "max_length": max_length,
                "proteins": proteins,
                "sequences": peptide_sequences,
                "n_proteins": len(proteins),
                "n_peptides": len(rows),
                "skipped_unsupported": skipped,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "enzyme": enzyme,
            "missed_cleavages": missed,
            "n_proteins": len(proteins),
            "n_peptides": len(rows),
            "skipped_unsupported": skipped,
            "min_length": min_length,
            "max_length": max_length,
        }
        print(
            f"protein_digest: {len(rows)} peptides from {len(proteins)} proteins "
            f"({enzyme}, missed={missed})"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
