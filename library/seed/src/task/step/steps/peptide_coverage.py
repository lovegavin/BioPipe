"""Protein sequence coverage of an in-silico peptide set."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._annotation_utils import fasta_sequences


def _merge(intervals):
    ordered = sorted(intervals)
    merged = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


class PeptideCoverageStep(Step):
    """Report how much of each protein is covered by observed peptides."""

    provider = "operon-core"
    parameters_file = "peptide_coverage.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "peptide_coverage",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peptide coverage",
        "description": (
            "Merge peptide intervals per protein and report covered residues, "
            "coverage fractions and peptide counts."
        ),
        "category": "Proteomics",
        "icon": "BarChart3",
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
                    "info": {"encoders": {"type": "object", "optional": True}},
                    "dims": [
                        {"param": "peptide_dim", "default": "peptide"},
                        {"param": "field_dim", "default": "field"},
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
        return max(size * 3, 32 * 2**20), 8 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        proteins, peptides = inputs
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        peptide_dim = str(params.get("peptide_dim", "peptide"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", self.name))

        names, sequences = fasta_sequences(
            proteins, sequence_dim, position_dim, "peptide_coverage"
        )
        names_info = peptides.info.get("proteins")
        if not isinstance(names_info, (list, tuple)) or not names_info:
            raise StepError("peptide_coverage: peptide table lacks info.proteins")
        field_positions = peptides.labels.get(field_dim, {})
        needed = ["protein_index", "start", "end"]
        missing = [name for name in needed if name not in field_positions]
        if missing:
            raise StepError(f"peptide_coverage: missing field(s) {', '.join(missing)}")
        index_of = {name: pos for pos, name in enumerate(names_info)}
        intervals = {}
        for row in peptides.data:
            name = str(names_info[int(round(float(row[field_positions["protein_index"]])))])
            start = int(round(float(row[field_positions["start"]])))
            end = int(round(float(row[field_positions["end"]])))
            if end < start:
                raise StepError("peptide_coverage: peptide end precedes start")
            intervals.setdefault(name, []).append((start - 1, end))

        rows = []
        labels = []
        for name, sequence in zip(names, sequences):
            spans = intervals.get(name, [])
            merged = _merge(spans) if spans else []
            covered = sum(end - start for start, end in merged)
            length = len(str(sequence))
            labels.append(name)
            rows.append(
                [
                    float(length),
                    float(covered),
                    float(covered) / float(length) if length else 0.0,
                    float(len(spans)),
                ]
            )
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data=data,
            dims=["protein", "statistic"],
            labels={
                "protein": {label: index for index, label in enumerate(labels)},
                "statistic": {
                    "protein_length": 0,
                    "covered_residues": 1,
                    "coverage_fraction": 2,
                    "n_peptides": 3,
                },
            },
            info={
                "n_proteins": len(rows),
                "n_peptides": int(data[:, 3].sum()),
                "mean_coverage": float(data[:, 2].mean()) if rows else 0.0,
                "unknown_proteins": sorted(set(intervals) - set(index_of)),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_proteins": len(rows),
            "n_peptides": int(data[:, 3].sum()),
            "mean_coverage": float(data[:, 2].mean()) if rows else 0.0,
            "proteins_covered": int((data[:, 2] > 0).sum()),
        }
        print(
            f"peptide_coverage: {len(rows)} proteins, "
            f"mean coverage {float(data[:, 2].mean()) if rows else 0.0:.3f}"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
