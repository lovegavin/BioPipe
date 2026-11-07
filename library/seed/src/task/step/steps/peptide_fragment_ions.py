"""Theoretical b/y fragment ions for a peptide table."""

from __future__ import annotations

import numpy as np
from operon_sdk import Form, Step, StepError

from ._ms_utils import fragment_ions


class PeptideFragmentIonsStep(Step):
    provider = "operon-core"
    parameters_file = "peptide_fragment_ions.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "peptide_fragment_ions",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peptide fragment ions",
        "description": "Compute theoretical b/y fragment ion m/z values for peptides with charge 1..N.",
        "category": "Proteomics",
        "icon": "Zap",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "name": "peptides",
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [{"param": "peptide_dim", "default": "peptide"}, {"param": "field_dim", "default": "field"}],
                    "labels": [],
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
        size = sum(int(getattr(item, "nbytes", 0) or 0) for item in inputs)
        return max(size * 3, 16 * 1024 * 1024), 16 * 1024 * 1024

    def run(self, ctx, inputs):
        params = ctx.step_params
        peptide_dim = params.get("peptide_dim", "peptide")
        field_dim = params.get("field_dim", "field")
        ion_types = tuple(
            item.strip().lower()
            for item in str(params.get("ion_types", "b,y")).split(",")
            if item.strip()
        )
        if not ion_types or any(item not in ("b", "y") for item in ion_types):
            raise StepError("peptide_fragment_ions: ion_types must be a subset of 'b,y'")
        max_charge = int(params.get("max_charge", 2))
        if not 1 <= max_charge <= 3:
            raise StepError("peptide_fragment_ions: max_charge must be between 1 and 3")
        out_name = params.get("output", "fragments")

        peptides = inputs[0]
        if len(getattr(peptides, "dims", [])) != 2:
            raise StepError("peptide_fragment_ions: input must be 2D")
        if peptide_dim not in peptides.labels or field_dim not in peptides.labels:
            raise StepError("peptide_fragment_ions: peptide table lacks the expected dimensions")
        sequences = peptides.info.get("sequences")
        if not sequences:
            raise StepError("peptide_fragment_ions: peptide Form lacks info.sequences")
        names = list(peptides.labels[peptide_dim])
        if len(sequences) != len(names):
            raise StepError("peptide_fragment_ions: info.sequences is not aligned with the peptide axis")

        rows = []
        labels = []
        for index, (name, sequence) in enumerate(zip(names, sequences)):
            text = str(sequence).strip().upper()
            for ion in fragment_ions(text, ion_types, max_charge):
                rows.append(
                    [
                        float(index),
                        float(len(labels) + 1),
                        0.0 if ion["type"] == "b" else 1.0,
                        float(ion["position"]),
                        float(ion["charge"]),
                        float(ion["mz"]),
                        float(ion["neutral"]),
                    ]
                )
                labels.append(f"{name}:{ion['type']}{ion['position']}{'+' * ion['charge']}")

        if not rows:
            raise StepError("peptide_fragment_ions: no fragments were generated")
        data = np.asarray(rows, dtype="float64")
        out = Form(
            data,
            dims=["fragment", "field"],
            labels={
                "fragment": {label: position for position, label in enumerate(labels)},
                "field": {
                    "peptide_index": 0,
                    "fragment_index": 1,
                    "ion_type": 2,
                    "position": 3,
                    "charge": 4,
                    "mz": 5,
                    "neutral_mass": 6,
                },
            },
            info={
                "ion_types": list(ion_types),
                "max_charge": max_charge,
                "n_peptides": len(names),
                "n_fragments": len(rows),
                "ion_type_codes": {"b": 0, "y": 1},
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_peptides": len(names),
            "n_fragments": len(rows),
            "ion_types": ",".join(ion_types),
            "max_charge": max_charge,
        }

    def export(self, ctx):
        return dict(self._export_data)
