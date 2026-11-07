# src/task/step/steps/genome_promoter_extract.py
"""Strand-aware upstream sequences (promoter windows) from an annotation."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._annotation_utils import (
    annotation_table,
    fasta_sequences,
    record_label,
    reverse_complement,
    select_type,
)


_CODE = {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4}


def _encode(sequence):
    return [_CODE.get(base, 4) for base in str(sequence).upper()]


class GenomePromoterExtractStep(Step):
    """Upstream sequence window for every feature, reverse-complemented on -."""

    provider = "operon-core"
    parameters_file = "genome_promoter_extract.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_promoter_extract",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Promoter window extraction",
        "description": (
            "Extract the upstream window of every gene or CDS, reverse "
            "complementing minus-strand features, and return an aligned "
            "sequence Form with FASTA-ready info.sequences."
        ),
        "category": "Genome",
        "icon": "Dna",
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
                        {"param": "record_dim", "default": "record"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
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
                },
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
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes)
        return max(size // 2, 8 * 2**20), 2 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        form, fasta = inputs[0], inputs[1]
        params = ctx.step_params
        record_dim = str(params.get("record_dim", "record"))
        field_dim = str(params.get("field_dim", "field"))
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        feature_type = str(params.get("feature_type", "gene")).strip() or "gene"
        upstream = int(params.get("upstream", 100))
        strand_aware = bool(params.get("strand_aware", True))
        include_feature = bool(params.get("include_feature", False))
        out_name = str(params.get("output", self.name))
        if upstream < 0:
            raise StepError("genome_promoter_extract: upstream must be >= 0")

        table = annotation_table(form, record_dim, field_dim, "genome_promoter_extract")
        chosen = select_type(table, feature_type, "genome_promoter_extract")
        names, sequences = fasta_sequences(
            fasta, sequence_dim, position_dim, "genome_promoter_extract"
        )
        genome = {name: sequence.upper() for name, sequence in zip(names, sequences)}

        rows = []
        labels = []
        strands = []
        lengths = []
        missing = []
        for index in chosen:
            seqid = table["seqid"][index]
            if seqid not in genome:
                missing.append(seqid)
                continue
            chrom = genome[seqid]
            start = int(table["start"][index])
            end = int(table["end"][index])
            strand = table["strand"][index]
            strand = strand if strand in ("+", "-") else "+"
            if strand == "-" and strand_aware:
                if include_feature:
                    window_start, window_end = start, end + upstream
                else:
                    window_start, window_end = end + 1, end + upstream
            else:
                if include_feature:
                    window_start, window_end = start - upstream, end
                else:
                    window_start, window_end = start - upstream, start - 1
            window_start = max(1, window_start)
            window_end = min(len(chrom), window_end)
            piece = chrom[window_start - 1:window_end] if window_end >= window_start else ""
            if strand == "-" and strand_aware:
                piece = reverse_complement(piece)
            fallback = f"{seqid}:{start}-{end}"
            label = f"{record_label(table['attributes'][index], fallback)}|{strand}"
            rows.append(_encode(piece))
            labels.append(label)
            strands.append(strand)
            lengths.append(len(piece))
        if missing:
            unique = sorted(set(missing))
            raise StepError(
                "genome_promoter_extract: annotation sequence(s) not in FASTA: "
                + ", ".join(unique[:5])
            )
        if not rows:
            raise StepError("genome_promoter_extract: no promoter windows produced")

        width = max(len(row) for row in rows)
        data = np.full((len(rows), width), 4, dtype=np.int16)
        info_sequences = []
        for position, row in enumerate(rows):
            data[position, : len(row)] = row
            info_sequences.append("".join("ACGTN"[code] for code in row))
        out = Form(
            data=data,
            dims=["promoter", "position"],
            labels={
                "promoter": {label: index for index, label in enumerate(labels)},
                "position": {str(i): i for i in range(width)},
            },
            info={
                "sequences": info_sequences,
                "alphabet_map": "ACGTN",
                "strand": strands,
                "lengths": lengths,
                "upstream": upstream,
                "feature_type": feature_type,
                "padded": len({length for length in lengths}) > 1,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "promoters": len(labels),
            "mean_length": float(np.mean(lengths)),
            "min_length": int(min(lengths)),
            "max_length": int(max(lengths)),
            "upstream": upstream,
            "feature_type": feature_type,
        }
        print(
            f"genome_promoter_extract: {len(labels)} promoters, "
            f"mean length {np.mean(lengths):.1f} bp (upstream {upstream})"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

