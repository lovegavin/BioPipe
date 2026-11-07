"""Report steric clashes between ligand heavy atoms and protein heavy atoms."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.base import Step
from src.task.step.steps.interface_bsa import vdw_radii


def _column(form: Form, dim: str, name: str) -> np.ndarray:
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise StepError(f"structure_ligand_clash: the structure form has no '{name}' column")
    return np.take(form.data, int(labels[name]), axis=list(form.dims).index(dim))


def _text_column(form: Form, dim: str, name: str) -> np.ndarray:
    values = _column(form, dim, name)
    encoders = (form.info or {}).get("encoders") or {}
    encoder = (encoders.get(dim) or {}).get(name)
    if isinstance(encoder, LabelEncoder):
        return np.array(encoder.inverse_transform(values), dtype=object)
    return np.array([f"{value:g}" for value in values], dtype=object)


def atom_table(form: Form, atom_dim: str, field_dim: str) -> dict[str, np.ndarray]:
    coords = np.column_stack([_column(form, field_dim, axis) for axis in ("x", "y", "z")])
    return {
        "coords": coords,
        "resname": _text_column(form, field_dim, "resname"),
        "chain": _text_column(form, field_dim, "chain"),
        "number": _column(form, field_dim, "residue_number"),
        "element": _text_column(form, field_dim, "element"),
        "atom_name": _text_column(form, field_dim, "atom_name"),
    }


def heavy_mask(elements: np.ndarray) -> np.ndarray:
    names = np.array([str(value).strip().upper() for value in elements], dtype=object)
    return ~np.isin(names, ["H", "D"])


def clash_rows(
    ligand_coords: np.ndarray,
    ligand_radii: np.ndarray,
    protein_coords: np.ndarray,
    protein_radii: np.ndarray,
    *,
    tolerance: float = 0.4,
    scale: float = 1.0,
) -> tuple[list[list[float]], int]:
    rows: list[list[float]] = []
    total = 0
    for index in range(len(ligand_coords)):
        distances = np.linalg.norm(protein_coords - ligand_coords[index], axis=1)
        overlaps = scale * (ligand_radii[index] + protein_radii) - distances
        clashing = overlaps > tolerance
        count = int(clashing.sum())
        total += count
        rows.append([float(count), float(overlaps.max()) if count else 0.0, float(distances.min())])
    return rows, total


class StructureLigandClashStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_clash.StructureLigandClashStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "structure_ligand_clash",
        "kind": "operator",
        "title": "Ligand steric clashes",
        "description": "Count van der Waals overlaps between ligand heavy atoms and protein heavy atoms, with per-atom worst overlap and closest distance.",
        "category": "Machine Learning",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim", "default": "atom"}, {"param": "field_dim", "default": "field"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("structure_ligand_clash: a PDB form input is required")
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim", "atom") or "atom")
        field_dim = str(ctx.step_params.get("field_dim", "field") or "field")
        residue_dim = str(ctx.step_params.get("atom_labels_dim", "ligand_atom") or "ligand_atom")
        out_name = ctx.step_params.get("output", "clashes") or "clashes"
        tolerance = ctx.step_params.get("tolerance")
        tolerance = 0.4 if tolerance is None else tolerance
        scale = ctx.step_params.get("clash_scale")
        scale = 1.0 if scale is None else scale
        ligand_text = str(ctx.step_params.get("ligand_resnames", "LIG") or "")
        ligand_names = {part.strip().upper() for part in ligand_text.replace(";", ",").split(",") if part.strip()}

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_ligand_clash: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )
        if not ligand_names:
            raise StepError("structure_ligand_clash: ligand_resnames must name at least one residue")
        if not isinstance(tolerance, (int, float)) or not 0.0 <= float(tolerance) <= 2.0:
            raise StepError("structure_ligand_clash: tolerance must be between 0 and 2 angstrom")
        if not isinstance(scale, (int, float)) or not 0.5 <= float(scale) <= 1.5:
            raise StepError("structure_ligand_clash: clash_scale must be between 0.5 and 1.5")

        table = atom_table(form, atom_dim, field_dim)
        heavy = heavy_mask(table["element"])
        is_ligand = np.array([str(value).strip().upper() in ligand_names for value in table["resname"]], dtype=bool)
        ligand = heavy & is_ligand
        protein = heavy & ~is_ligand
        if int(ligand.sum()) == 0:
            raise StepError(
                "structure_ligand_clash: no ligand heavy atom matches ligand_resnames "
                f"'{ctx.step_params.get('ligand_resnames', 'LIG')}'"
            )
        if int(protein.sum()) == 0:
            raise StepError("structure_ligand_clash: the structure has no protein heavy atoms")

        radii = vdw_radii(table["element"])
        rows, total = clash_rows(
            table["coords"][ligand],
            radii[ligand],
            table["coords"][protein],
            radii[protein],
            tolerance=float(tolerance),
            scale=float(scale),
        )
        ligand_labels = [
            f"{table['chain'][index]}:{table['resname'][index]}:{int(round(float(table['number'][index])))}:"
            f"{str(table['atom_name'][index]).strip()}"
            for index in np.flatnonzero(ligand)
        ]
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(ligand_labels)},
                "statistic": {"n_clashes": 0, "worst_overlap": 1, "min_distance": 2},
            },
            info={
                "missing_code": np.nan,
                "ligand_resnames": sorted(ligand_names),
                "n_ligand_atoms": int(ligand.sum()),
                "n_protein_atoms": int(protein.sum()),
                "n_clashes": int(total),
                "tolerance": float(tolerance),
                "clash_scale": float(scale),
                "unit": "angstrom",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_ligand_atoms": int(ligand.sum()),
            "n_protein_atoms": int(protein.sum()),
            "n_clashes": int(total),
            "tolerance": float(tolerance),
            "clash_scale": float(scale),
            "ligand_resnames": sorted(ligand_names),
        }
        print(f"[structure_ligand_clash] {int(ligand.sum())} ligand atoms, {total} clashes")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
