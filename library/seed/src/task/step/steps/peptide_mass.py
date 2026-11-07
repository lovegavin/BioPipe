"""Monoisotopic peptide mass and m/z for a peptide table."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._proteomics_utils import peptide_mass, peptide_mz


class PeptideMassStep(Step):
    """Compute monoisotopic masses and m/z values for a peptide table."""

    provider = "operon-core"
    parameters_file = "peptide_mass.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "peptide_mass",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peptide mass and m/z",
        "description": (
            "Compute monoisotopic peptide masses from the sequences carried "
            "by a peptide Form and convert them to m/z for a given charge."
        ),
        "category": "Proteomics",
        "icon": "Calculator",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "peptide_dim", "default": "peptide"},
                        {"param": "field_dim", "default": "field"},
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
        return max(size * 3, 16 * 2**20), 8 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        peptides = inputs[0]
        params = ctx.step_params
        peptide_dim = str(params.get("peptide_dim", "peptide"))
        charge = int(params.get("charge", 2))
        out_name = str(params.get("output", self.name))
        if charge < 1:
            raise StepError("peptide_mass: charge must be >= 1")

        sequences = peptides.info.get("sequences")
        labels = peptides.labels.get(peptide_dim, {})
        if not isinstance(sequences, (list, tuple)) or len(sequences) != len(labels):
            raise StepError("peptide_mass: peptide Form lacks info.sequences")
        if not sequences:
            raise StepError("peptide_mass: peptide table is empty")

        ordered = sorted(labels.items(), key=lambda item: item[1])
        rows = []
        for label, _ in ordered:
            sequence = str(sequences[labels[label]]).upper()
            if not sequence:
                raise StepError(f"peptide_mass: empty peptide {label!r}")
            mass = peptide_mass(sequence, label)
            rows.append([mass, peptide_mz(mass, charge)])
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data=data,
            dims=["peptide", "statistic"],
            labels={
                "peptide": {label: index for index, (label, _) in enumerate(ordered)},
                "statistic": {
                    "monoisotopic_mass": 0,
                    "mz": 1,
                },
            },
            info={
                "charge": charge,
                "n_peptides": len(rows),
                "mass_range": [
                    float(data[:, 0].min()),
                    float(data[:, 0].max()),
                ],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "charge": charge,
            "n_peptides": len(rows),
            "min_mass": float(data[:, 0].min()),
            "max_mass": float(data[:, 0].max()),
        }
        print(f"peptide_mass: {len(rows)} peptides at charge {charge}")

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
