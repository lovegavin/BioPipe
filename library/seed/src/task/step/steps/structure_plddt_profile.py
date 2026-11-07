"""Per-residue pLDDT profile of a predicted structure."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, has_column, residue_labels

_STATISTICS = ("mean_plddt", "min_plddt", "max_plddt", "n_atoms")


class StructurePlddtProfileStep(Step):
    """Mean B-factor (pLDDT) per residue of a predicted PDB structure."""

    provider = "operon-core"

    parameters_file = "structure_plddt_profile.StructurePlddtProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_plddt_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Per-residue pLDDT profile",
        "description": (
            "Aggregate the B-factor column of a predicted structure (ESMFold, ColabFold or "
            "AlphaFold write pLDDT there) into one row per residue with mean, minimum and "
            "maximum confidence and the number of contributing atoms."
        ),
        "category": "Structure",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        (form,) = inputs
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        residue_dim = str(params.get("residue_dim") or "residue")
        out_name = str(params.get("output") or "plddt")

        if len(np.asarray(form.data)) == 0:
            raise StepError("structure_plddt_profile: the structure form is empty")
        if not has_column(form, field_dim, "bfactor"):
            raise StepError(
                "structure_plddt_profile: the structure form has no 'bfactor' column; "
                "read a predicted PDB with PdbReader so pLDDT lands in that column"
            )

        values = np.asarray(form.data[:, column_index(form, field_dim, "bfactor")], dtype=np.float64)
        labels = np.asarray(residue_labels(form, field_dim), dtype=object)
        finite = np.isfinite(values)
        if not finite.any():
            raise StepError("structure_plddt_profile: no atom carries a finite pLDDT value")

        order: dict[str, list[int]] = {}
        for index, label in enumerate(labels):
            if not finite[index]:
                continue
            order.setdefault(str(label), []).append(index)
        if not order:
            raise StepError("structure_plddt_profile: no residue carries a finite pLDDT value")

        residue_names = list(order)
        rows = []
        for name in residue_names:
            selected = values[order[name]]
            rows.append(
                (
                    float(selected.mean()),
                    float(selected.min()),
                    float(selected.max()),
                    float(len(selected)),
                )
            )
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {name: index for index, name in enumerate(residue_names)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "mean_plddt": float(values[finite].mean()),
                "median_plddt": float(np.median(values[finite])),
                "min_plddt": float(values[finite].min()),
                "max_plddt": float(values[finite].max()),
                "n_residues": len(residue_names),
                "n_atoms": int(finite.sum()),
                "scale": "hundred" if float(values[finite].max()) > 1.0 else "fraction",
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "mean_plddt": float(values[finite].mean()),
            "min_plddt": float(values[finite].min()),
            "max_plddt": float(values[finite].max()),
            "n_residues": len(residue_names),
        }
        print(
            f"[structure_plddt_profile] {len(residue_names)} residues, "
            f"mean pLDDT {values[finite].mean():.2f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
