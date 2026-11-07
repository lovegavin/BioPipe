"""Theoretical isotope envelopes for a peptide table."""

from __future__ import annotations

import numpy as np
from biopipe_sdk import Form, Step, StepError

from ._ms_utils import isotope_envelope


class PeptideIsotopeEnvelopeStep(Step):
    provider = "biopipe-core"
    parameters_file = "peptide_isotope_envelope.parameters.json"

    definition = {
        "protocol_version": 3,
        "id": "peptide_isotope_envelope",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peptide isotope envelope",
        "description": "Compute the top theoretical isotope peaks (m/z, fraction, relative intensity) per peptide.",
        "category": "Proteomics",
        "icon": "Waves",
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
        return max(size * 2, 8 * 1024 * 1024), 8 * 1024 * 1024

    def run(self, ctx, inputs):
        params = ctx.step_params
        peptide_dim = params.get("peptide_dim", "peptide")
        field_dim = params.get("field_dim", "field")
        max_peaks = int(params.get("max_peaks", 4))
        charge = int(params.get("charge", 1))
        # charge only widens spacing; the operator reports singly charged default
        if not 1 <= max_peaks <= 8:
            raise StepError("peptide_isotope_envelope: max_peaks must be between 1 and 8")
        if not 1 <= charge <= 3:
            raise StepError("peptide_isotope_envelope: charge must be between 1 and 3")
        out_name = params.get("output", "envelope")

        peptides = inputs[0]
        if len(getattr(peptides, "dims", [])) != 2:
            raise StepError("peptide_isotope_envelope: input must be 2D")
        if peptide_dim not in peptides.labels or field_dim not in peptides.labels:
            raise StepError("peptide_isotope_envelope: peptide table lacks the expected dimensions")
        sequences = peptides.info.get("sequences")
        if not sequences:
            raise StepError("peptide_isotope_envelope: peptide Form lacks info.sequences")
        names = list(peptides.labels[peptide_dim])
        if len(sequences) != len(names):
            raise StepError("peptide_isotope_envelope: info.sequences is not aligned with the peptide axis")

        columns = {}
        for index in range(max_peaks):
            columns[f"mz_{index}"] = []
            columns[f"fraction_{index}"] = []
            columns[f"intensity_{index}"] = []
        for sequence in sequences:
            envelope = isotope_envelope(str(sequence).strip().upper(), "peptide_isotope_envelope", max_peaks, charge)
            for index in range(max_peaks):
                if index < len(envelope):
                    peak = envelope[index]
                    columns[f"mz_{index}"].append(peak["mz"])
                    columns[f"fraction_{index}"].append(peak["fraction"])
                    columns[f"intensity_{index}"].append(peak["intensity"])
                else:
                    columns[f"mz_{index}"].append(0.0)
                    columns[f"fraction_{index}"].append(0.0)
                    columns[f"intensity_{index}"].append(0.0)

        data = np.column_stack([np.asarray(columns[key], dtype="float64") for key in columns])
        fields = {}
        for position, key in enumerate(columns):
            fields[key] = position
        out = Form(
            data,
            dims=["peptide", "peak"],
            labels={
                "peptide": {name: position for position, name in enumerate(names)},
                "peak": fields,
            },
            info={
                "max_peaks": max_peaks,
                "charge": charge,
                "n_peptides": len(names),
                "field_order": list(fields),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_peptides": len(names),
            "max_peaks": max_peaks,
            "charge": charge,
        }

    def export(self, ctx):
        return dict(self._export_data)
