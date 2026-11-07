"""Precursor masses with fixed modifications for a peptide table."""

from __future__ import annotations

import numpy as np
from operon_sdk import Form, Step, StepError

from ._ms_utils import modified_mass, parse_mods


class PeptideModifiedMassStep(Step):
    provider = "operon-core"
    parameters_file = "peptide_modified_mass.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "peptide_modified_mass",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Modified peptide mass",
        "description": "Compute unmodified and fixed-modification precursor masses for peptides.",
        "category": "Proteomics",
        "icon": "Calculator",
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
        out_name = params.get("output", "modified")
        fixed_mods = parse_mods(params.get("fixed_mods", "C:57.02146372"), "peptide_modified_mass")

        peptides = inputs[0]
        if len(getattr(peptides, "dims", [])) != 2:
            raise StepError("peptide_modified_mass: input must be 2D")
        if peptide_dim not in peptides.labels or field_dim not in peptides.labels:
            raise StepError("peptide_modified_mass: peptide table lacks the expected dimensions")
        sequences = peptides.info.get("sequences")
        if not sequences:
            raise StepError("peptide_modified_mass: peptide Form lacks info.sequences")
        names = list(peptides.labels[peptide_dim])
        if len(sequences) != len(names):
            raise StepError("peptide_modified_mass: info.sequences is not aligned with the peptide axis")

        rows = []
        sites = []
        for sequence in sequences:
            base, modified, shift, count = modified_mass(
                str(sequence).strip().upper(), fixed_mods, "peptide_modified_mass"
            )
            rows.append([base, modified, shift])
            sites.append(float(count))

        data = np.asarray(rows, dtype="float64")
        out = Form(
            data,
            dims=["peptide", "statistic"],
            labels={
                "peptide": {name: position for position, name in enumerate(names)},
                "statistic": {"unmodified_mass": 0, "modified_mass": 1, "mass_shift": 2},
            },
            info={
                "fixed_mods": {key: float(value) for key, value in fixed_mods.items()},
                "n_peptides": len(names),
                "n_modified": int(sum(1 for value in sites if value > 0)),
                "modification_sites_min": int(min(sites)),
                "modification_sites_max": int(max(sites)),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_peptides": len(names),
            "n_modified": int(sum(1 for value in sites if value > 0)),
            "fixed_mods": ",".join(f"{key}:{value:.5f}" for key, value in fixed_mods.items()),
        }

    def export(self, ctx):
        return dict(self._export_data)
