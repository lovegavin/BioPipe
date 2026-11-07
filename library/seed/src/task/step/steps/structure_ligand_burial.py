"""Ligand burial from solvent-accessible surface area."""

from __future__ import annotations

import numpy as np
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, split_chains
from src.task.step.steps._structure_common import field_columns, heavy_atom_mask
from src.task.step.steps.interface_bsa import sasa_per_atom, vdw_radii

STATISTICS = ("n_atoms", "sasa_alone", "sasa_complex", "buried_fraction")


def ligand_groups(
    form: Form, atom_dim: str, field_dim: str, resnames: list[str], chains: list[str]
) -> list[dict]:
    """Group ligand atoms per residue and gather the protein atoms."""
    fields = ("chain", "resname", "residue_number", "element", "x", "y", "z")
    field_columns(form, field_dim, fields)
    chain_ids = decode_column(form, field_dim, "chain")
    residue_names = decode_column(form, field_dim, "resname")
    numbers = decode_column(form, field_dim, "residue_number")
    elements = decode_column(form, field_dim, "element")
    coords = np.column_stack(
        [
            np.asarray(form.data[:, form.labels[field_dim][axis]], dtype=float)
            for axis in ("x", "y", "z")
        ]
    )
    mask = heavy_atom_mask(form, field_dim)
    radii_all = vdw_radii(elements)
    groups: dict[str, dict] = {}
    protein_coords: list[np.ndarray] = []
    protein_radii: list[float] = []
    order: list[str] = []
    for index in range(len(chain_ids)):
        if not mask[index]:
            continue
        chain = str(chain_ids[index]).strip()
        if chains and chain not in chains:
            continue
        name = str(residue_names[index]).strip().upper()
        if name in resnames:
            label = f"{chain}:{name}:{numbers[index]}"
            group = groups.get(label)
            if group is None:
                group = {"label": label, "coords": [], "radii": []}
                groups[label] = group
                order.append(label)
            group["coords"].append(coords[index])
            group["radii"].append(radii_all[index])
        else:
            protein_coords.append(coords[index])
            protein_radii.append(radii_all[index])
    return [
        {
            "label": label,
            "coords": np.stack(groups[label]["coords"]),
            "radii": np.asarray(groups[label]["radii"], dtype=float),
        }
        for label in order
    ], protein_coords, protein_radii


def burial_rows(
    groups: list[dict],
    protein_coords: list[np.ndarray],
    protein_radii: list[float],
    *,
    probe_radius: float = 1.4,
    n_points: int = 92,
) -> list[dict]:
    rows: list[dict] = []
    for group in groups:
        alone = sasa_per_atom(
            np.asarray(group["coords"], float),
            np.asarray(group["radii"], float),
            probe_radius=probe_radius,
            n_points=n_points,
        )
        ligand_count = len(alone)
        combined_coords = np.vstack(
            [np.asarray(group["coords"], float)] + [np.asarray(item) for item in protein_coords]
        ) if protein_coords else np.asarray(group["coords"], float)
        combined_radii = np.concatenate(
            [
                np.asarray(group["radii"], float),
                np.asarray(protein_radii, dtype=float),
            ]
        ) if protein_radii else np.asarray(group["radii"], float)
        combined = sasa_per_atom(
            combined_coords,
            combined_radii,
            probe_radius=probe_radius,
            n_points=n_points,
        )[:ligand_count]
        total_alone = float(np.sum(alone))
        total_complex = float(np.sum(combined))
        fraction = 0.0
        if total_alone > 0:
            fraction = max(0.0, min(1.0, 1.0 - total_complex / total_alone))
        rows.append(
            {
                "label": group["label"],
                "n_atoms": ligand_count,
                "sasa_alone": total_alone,
                "sasa_complex": total_complex,
                "buried_fraction": fraction,
            }
        )
    return rows


class StructureLigandBurialStep(Step):
    """Buried fraction of ligand surface area inside a protein structure."""

    provider = "operon-core"
    parameters_file = "structure_ligand_burial.StructureLigandBurialStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_burial",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand burial",
        "description": (
            "Computes solvent-accessible surface area of each ligand residue alone and "
            "in the protein complex and reports the buried fraction."
        ),
        "category": "Machine Learning",
        "icon": "Columns",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        ligand_dim = str(params.get("ligand_dim", "ligand"))
        out_name = str(params.get("output", "burial"))
        resnames = [name.strip().upper() for name in split_chains(str(params.get("ligand_resnames", "LIG")))]
        if not resnames:
            raise StepError(
                "structure_ligand_burial: ligand_resnames must name at least one residue"
            )
        chains = split_chains(str(params.get("chains", "")))
        probe_radius = float(params.get("probe_radius", 1.4))
        n_points = int(params.get("n_points", 92))
        if not 1.0 <= probe_radius <= 3.0:
            raise StepError(
                "structure_ligand_burial: probe_radius must be between 1.0 and 3.0"
            )
        if not 32 <= n_points <= 1024:
            raise StepError(
                "structure_ligand_burial: n_points must be between 32 and 1024"
            )

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_ligand_burial: a structure form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        groups, protein_coords, protein_radii = ligand_groups(
            form, atom_dim, field_dim, resnames, chains
        )
        if not groups:
            raise StepError(
                "structure_ligand_burial: no ligand residue matches ligand_resnames "
                f"'{', '.join(resnames)}'"
            )
        if not protein_coords:
            raise StepError(
                "structure_ligand_burial: the structure form has no protein atoms to "
                "bury the ligand in"
            )
        rows = burial_rows(
            groups,
            protein_coords,
            protein_radii,
            probe_radius=probe_radius,
            n_points=n_points,
        )
        labels = [row["label"] for row in rows]
        data = np.asarray(
            [
                [
                    row["n_atoms"],
                    row["sasa_alone"],
                    row["sasa_complex"],
                    row["buried_fraction"],
                ]
                for row in rows
            ],
            dtype=np.float32,
        )
        out = Form(
            data=data,
            dims=[ligand_dim, "statistic"],
            labels={
                ligand_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {
                    name: index for index, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_ligands": len(labels),
                "resnames": resnames,
                "probe_radius": probe_radius,
                "n_points": n_points,
                "unit": "A^2",
            },
        )
        out.validate()
        self._export_data = {
            "n_ligands": len(labels),
            "mean_buried_fraction": float(data[:, 3].mean()),
            "most_buried": labels[int(np.argmax(data[:, 3]))],
            "total_sasa_alone": float(data[:, 1].sum()),
        }
        ctx[out_name] = out
        print(
            f"[structure_ligand_burial] {len(labels)} ligands, mean buried "
            f"{self._export_data['mean_buried_fraction']:.3f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
