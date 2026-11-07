"""Zinc coordination sites in a PDB structure form.

A structural zinc site is a zinc ion surrounded by cysteine thiolates and
histidine imidazole nitrogens at bonding distance.  The operator scans the
heavy-atom table for zinc atoms, collects protein S/N donors within the
coordination cutoff, and reports one row per site with the ligand count and the
mean and minimum Zn-donor distance.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column

_STATISTICS = ("n_ligands", "mean_distance", "min_distance")
_REQUIRED = ("x", "y", "z", "element", "resname", "chain", "residue_number")
_DONOR_ELEMENTS = frozenset({"S", "N"})
_DONOR_NAMES = frozenset({"SG", "ND1", "NE2"})


def _column(form: Form, field_dim: str, name: str, operator: str) -> np.ndarray:
    values = decode_column(form, field_dim, name)
    if values is None:
        raise StepError(
            f"{operator}: the structure form has no '{name}' column"
        )
    return values


def atom_labels(form: Form, field_dim: str) -> np.ndarray:
    """Build ``chain:resname:number`` residue labels for every atom row."""

    chains = _column(form, field_dim, "chain", "structure_zinc_sites")
    names = _column(form, field_dim, "resname", "structure_zinc_sites")
    numbers = _column(form, field_dim, "residue_number", "structure_zinc_sites")
    return np.array(
        [
            f"{chain}:{name}:{number}"
            for chain, name, number in zip(chains, names, numbers)
        ],
        dtype=object,
    )


def zinc_sites(
    coordinates: np.ndarray,
    elements: np.ndarray,
    atom_names: np.ndarray | None,
    residue_labels: np.ndarray,
    *,
    cutoff: float = 2.9,
    min_ligands: int = 3,
) -> list[dict]:
    """Return one record per zinc ion with at least ``min_ligands`` donors."""

    uppercased = np.char.upper(np.asarray(elements, dtype=str))
    zinc_index = np.flatnonzero(uppercased == "ZN")
    if zinc_index.size == 0:
        raise StepError(
            "structure_zinc_sites: the structure form has no zinc atoms"
        )
    element_ok = np.isin(uppercased, list(_DONOR_ELEMENTS))
    if atom_names is None:
        donor_mask = element_ok
    else:
        names = np.char.upper(np.asarray(atom_names, dtype=str))
        donor_mask = np.isin(names, list(_DONOR_NAMES)) & element_ok
    donor_index = np.flatnonzero(donor_mask)
    if donor_index.size == 0:
        raise StepError(
            "structure_zinc_sites: the structure form carries no cysteine SG or "
            "histidine ND1/NE2 donor atoms"
        )
    records: list[dict] = []
    for zinc in zinc_index:
        deltas = coordinates[donor_index] - coordinates[zinc]
        distances = np.linalg.norm(deltas, axis=1)
        close = np.flatnonzero(distances <= cutoff)
        if close.size < min_ligands:
            continue
        selected = donor_index[close]
        records.append(
            {
                "zinc": int(zinc),
                "zinc_label": str(residue_labels[zinc]),
                "n_ligands": int(close.size),
                "mean_distance": float(distances[close].mean()),
                "min_distance": float(distances[close].min()),
                "ligands": [
                    {
                        "residue": str(residue_labels[index]),
                        "atom": str(atom_names[index]) if atom_names is not None else "",
                        "distance": float(distances[position]),
                    }
                    for position, index in zip(close, selected)
                ],
            }
        )
    return records


class StructureZincSitesStep(Step):
    """Structural zinc sites from Cys/His coordination geometry."""

    provider = "operon-core"

    parameters_file = (
        "structure_zinc_sites.StructureZincSitesStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_zinc_sites",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structural zinc sites",
        "description": (
            "Find zinc ions in a PDB atom table and report the cysteine and "
            "histidine atoms within coordination distance, with ligand counts "
            "and Zn-donor distances."
        ),
        "category": "Structure",
        "icon": "Atom",
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        cutoff = float(params.get("coordination_cutoff") or 2.9)
        min_ligands = int(params.get("min_ligands") or 3)
        out_name = params.get("output", self.name)

        if not 1.5 <= cutoff <= 4.0:
            raise StepError(
                "structure_zinc_sites: coordination_cutoff must be between 1.5 "
                "and 4.0 angstrom"
            )
        if not 1 <= min_ligands <= 8:
            raise StepError(
                "structure_zinc_sites: min_ligands must be between 1 and 8"
            )
        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_zinc_sites: expected a "
                f"[{atom_dim}, {field_dim}] structure form, got {list(form.dims)}"
            )
        for name in _REQUIRED:
            if decode_column(form, field_dim, name) is None:
                raise StepError(
                    f"structure_zinc_sites: the structure form has no '{name}' "
                    "column"
                )
        coordinates = np.asarray(form.data, dtype=np.float64)
        fields = form.labels[field_dim]
        columns = []
        for name in ("x", "y", "z"):
            position = int(fields[name])
            columns.append(coordinates[:, position])
        points = np.column_stack(columns)
        elements = _column(form, field_dim, "element", "structure_zinc_sites")
        atom_names = decode_column(form, field_dim, "atom_name")
        labels = atom_labels(form, field_dim)
        records = zinc_sites(
            points,
            elements,
            atom_names,
            labels,
            cutoff=cutoff,
            min_ligands=min_ligands,
        )
        if not records:
            raise StepError(
                "structure_zinc_sites: no zinc site reaches min_ligands "
                f"({min_ligands}) coordinating atoms within {cutoff:g} angstrom"
            )
        rows = [
            (
                float(record["n_ligands"]),
                record["mean_distance"],
                record["min_distance"],
            )
            for record in records
        ]
        form_out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["site", "statistic"],
            labels={
                "site": {
                    f"zn{index + 1}:{record['zinc_label']}": index
                    for index, record in enumerate(records)
                },
                "statistic": {
                    name: position for position, name in enumerate(_STATISTICS)
                },
            },
            info={
                "n_sites": len(records),
                "coordination_cutoff": cutoff,
                "min_ligands": min_ligands,
                "sites": records,
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_sites": len(records),
            "max_ligands": max(record["n_ligands"] for record in records),
        }
        print(f"[{self.name}] {len(records)} zinc site(s)")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
