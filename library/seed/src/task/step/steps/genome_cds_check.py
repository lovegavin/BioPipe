# src/task/step/steps/genome_cds_check.py
"""Coding-sequence sanity check against the genome FASTA."""
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
    translate_dna,
    unique_labels,
)


_STATISTICS = (
    "length_ok",
    "start_ok",
    "stop_ok",
    "internal_stops",
    "protein_length",
)
_START_CODONS = frozenset({"ATG", "GTG", "TTG"})
_STOP_CODONS = frozenset({"TAA", "TAG", "TGA"})


class GenomeCdsCheckStep(Step):
    """Length, start/stop codon and internal-stop check for CDS records."""

    provider = "operon-core"
    parameters_file = "genome_cds_check.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_cds_check",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CDS translation check",
        "description": (
            "Translate every CDS from the genome FASTA and report frame, "
            "start codon, stop codon and internal stop statistics."
        ),
        "category": "Genome",
        "icon": "CheckCircle",
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
        feature_type = str(params.get("feature_type", "CDS")).strip() or "CDS"
        out_name = str(params.get("output", self.name))

        table = annotation_table(form, record_dim, field_dim, "genome_cds_check")
        chosen = select_type(table, feature_type, "genome_cds_check")
        names, sequences = fasta_sequences(
            fasta, sequence_dim, position_dim, "genome_cds_check"
        )
        genome = {name: sequence.upper() for name, sequence in zip(names, sequences)}

        rows = []
        labels = []
        per_seqid = []
        missing = []
        for index in chosen:
            seqid = table["seqid"][index]
            if seqid not in genome:
                missing.append(seqid)
                continue
            chrom = genome[seqid]
            start = int(table["start"][index])
            end = int(table["end"][index])
            if start < 1 or end > len(chrom):
                raise StepError(
                    f"genome_cds_check: {seqid}:{start}-{end} outside sequence "
                    f"length {len(chrom)}"
                )
            coding = chrom[start - 1:end]
            if table["strand"][index] == "-":
                coding = reverse_complement(coding)
            length_ok = 1.0 if len(coding) % 3 == 0 else 0.0
            protein = translate_dna(coding)
            start_ok = 1.0 if coding[:3] in _START_CODONS else 0.0
            stop_ok = 1.0 if coding[-3:] in _STOP_CODONS else 0.0
            if length_ok and protein.endswith("*"):
                internal = protein[:-1].count("*")
            else:
                internal = protein.count("*")
            fallback = f"{seqid}:{start}-{end}"
            labels.append(record_label(table["attributes"][index], fallback))
            per_seqid.append(seqid)
            rows.append([length_ok, start_ok, stop_ok, internal, len(coding) // 3])
        if missing:
            unique = sorted(set(missing))
            raise StepError(
                "genome_cds_check: annotation sequence(s) not in FASTA: "
                + ", ".join(unique[:5])
            )
        if not rows:
            raise StepError("genome_cds_check: no CDS records produced")
        labels = unique_labels(labels)

        data = np.asarray(rows, dtype=np.float32).reshape(-1, len(_STATISTICS))
        out = Form(
            data=data,
            dims=["cds", "statistic"],
            labels={
                "cds": {label: index for index, label in enumerate(labels)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "feature_type": feature_type,
                "seqid": per_seqid,
                "n_cds": len(labels),
            },
        )
        out.validate()
        ctx[out_name] = out
        summary = {
            "cds": len(labels),
            "length_ok": int(data[:, 0].sum()),
            "start_ok": int(data[:, 1].sum()),
            "stop_ok": int(data[:, 2].sum()),
            "with_internal_stops": int((data[:, 3] > 0).sum()),
            "feature_type": feature_type,
        }
        self._export_data = summary
        print(
            f"genome_cds_check: {summary['cds']} CDS, length_ok "
            f"{summary['length_ok']}, start_ok {summary['start_ok']}, "
            f"stop_ok {summary['stop_ok']}, internal stops "
            f"{summary['with_internal_stops']}"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

