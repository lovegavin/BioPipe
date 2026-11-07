"""Pairwise CA-CA distance matrix for a structure form."""

from __future__ import annotations

import numpy as np
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, split_chains
from src.task.step.steps._structure_common import field_columns, heavy_atom_mask


def ca_atoms(form: Form, atom_dim: str, field_dim: str, chains: list[str]) -> list[dict]:
    """Return one CA entry per residue in structure order."""
    fields = ("atom_name", "chain", "residue_number", "resname", "x", "y", "z")
    field_columns(form, field_dim, fields)
    atom_names = decode_column(form, field_dim, "atom_name")
    chain_ids = decode_column(form, field_dim, "chain")
    numbers = decode_column(form, field_dim, "residue_number")
    resnames = decode_column(form, field_dim, "resname")
    coords = np.column_stack(
        [
            np.asarray(form.data[:, form.labels[field_dim][axis]], dtype=float)
            for axis in ("x", "y", "z")
        ]
    )
    mask = heavy_atom_mask(form, field_dim)
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index in range(len(atom_names)):
        if not mask[index]:
            continue
        if str(atom_names[index]).strip().upper() != "CA":
            continue
        chain = str(chain_ids[index]).strip()
        if chains and chain not in chains:
            continue
        key = (chain, str(numbers[index]))
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "label": f"{chain}:{_resname(resnames[index], chain)}:{numbers[index]}",
                "chain": chain,
                "number": numbers[index],
                "coord": coords[index],
            }
        )
    return entries


def _resname(value, chain: str) -> str:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return "UNK"
    return text


def distance_matrix(entries: list[dict]) -> np.ndarray:
    coords = np.stack([entry["coord"] for entry in entries])
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=-1))


class StructureCaDistanceMatrixStep(Step):
    """Pairwise CA-CA distances with an optional chain filter."""

    provider = "operon-core"
    parameters_file = (
        "structure_ca_distance_matrix.StructureCaDistanceMatrixStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ca_distance_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CA distance matrix",
        "description": (
            "Builds a symmetric residue-by-residue CA-CA distance matrix from a "
            "full-atom PDB form, optionally restricted to selected chains."
        ),
        "category": "Machine Learning",
        "icon": "ChartScatter",
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
        residue_dim = str(params.get("residue_dim", "residue"))
        other_dim = str(params.get("other_residue_dim", "residue_b"))
        out_name = str(params.get("output", "ca_distances"))
        wanted = split_chains(str(params.get("chains", "")))
        if residue_dim == other_dim:
            raise StepError(
                "structure_ca_distance_matrix: residue_dim and other_residue_dim must differ"
            )

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_ca_distance_matrix: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        entries = ca_atoms(form, atom_dim, field_dim, wanted)
        if len(entries) < 2:
            raise StepError(
                "structure_ca_distance_matrix: at least two residues with a CA atom are required"
            )
        if wanted:
            present = {entry["chain"] for entry in entries}
            missing = sorted(set(wanted) - present)
            if missing:
                raise StepError(
                    "structure_ca_distance_matrix: chain(s) "
                    f"{', '.join(missing)} were not found in the structure form"
                )
        labels = [entry["label"] for entry in entries]
        matrix = distance_matrix(entries).astype(np.float32)
        out = Form(
            data=matrix,
            dims=[residue_dim, other_dim],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                other_dim: {label: index for index, label in enumerate(labels)},
            },
            info={
                "missing_code": np.nan,
                "n_residues": len(labels),
                "residues": labels,
                "chains": sorted({entry["chain"] for entry in entries}),
                "unit": "A",
            },
        )
        out.validate()
        off_diagonal = matrix[~np.eye(len(labels), dtype=bool)]
        self._export_data = {
            "n_residues": len(labels),
            "chains": sorted({entry["chain"] for entry in entries}),
            "min_distance": float(off_diagonal.min()),
            "max_distance": float(off_diagonal.max()),
            "mean_distance": float(off_diagonal.mean()),
        }
        ctx[out_name] = out
        print(
            f"[structure_ca_distance_matrix] {len(labels)} CA atoms, "
            f"range {off_diagonal.min():.2f}-{off_diagonal.max():.2f} A"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
