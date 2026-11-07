"""Alternate-conformer inventory of a PDB structure.

Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``.
Output: 2D Form ``[altloc, statistic]`` with atom/residue counts and
occupancy statistics per conformer identifier.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._protein_common import residue_labels as _residue_labels
from ._structure_checks import altloc_column, occupancy_column

_STATISTIC = {
    "n_atoms": 0,
    "n_residues": 1,
    "min_occupancy": 2,
    "max_occupancy": 3,
    "mean_occupancy": 4,
}


def altloc_rows(form, atom_dim: str, field_dim: str) -> tuple[list[dict], dict]:
    """Aggregate atoms and occupancy statistics per altloc identifier."""
    altlocs = altloc_column(form, field_dim)
    occupancy = occupancy_column(form, field_dim)
    try:
        labels = _residue_labels(form, field_dim)
    except StepError:
        labels = None

    groups: dict[str, dict] = {}
    for index in range(len(altlocs)):
        alt = str(altlocs[index])
        group = groups.setdefault(alt, {"n_atoms": 0, "residues": set(), "occupancy": []})
        group["n_atoms"] += 1
        if labels is not None:
            group["residues"].add(str(labels[index]))
        value = float(occupancy[index])
        if np.isfinite(value):
            group["occupancy"].append(value)

    rows: list[dict] = []
    for alt in sorted(groups, key=lambda name: (name != "_", name)):
        group = groups[alt]
        values = np.asarray(group["occupancy"], dtype=float)
        rows.append(
            {
                "altloc": alt,
                "n_atoms": group["n_atoms"],
                "n_residues": len(group["residues"]),
                "min_occupancy": float(values.min()) if values.size else float("nan"),
                "max_occupancy": float(values.max()) if values.size else float("nan"),
                "mean_occupancy": float(values.mean()) if values.size else float("nan"),
            }
        )

    alternates: dict[str, set] = {}
    for index in range(len(altlocs)):
        alt = str(altlocs[index])
        if alt == "_" or labels is None:
            continue
        alternates.setdefault(str(labels[index]), set()).add(alt)
    summary = {
        "n_altloc_atoms": int(sum(1 for value in altlocs if str(value) != "_")),
        "n_residues_with_alternates": int(
            sum(1 for conformers in alternates.values() if len(conformers) >= 2)
        ),
        "altlocs": [row["altloc"] for row in rows],
    }
    return rows, summary


class StructureAltlocInventoryStep(Step):
    """Inventory alternate conformers and their occupancies."""

    provider = "operon-core"
    parameters_file = "structure_altloc_inventory.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_altloc_inventory",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Alternate conformer inventory",
        "description": (
            "Counts atoms and residues per altloc identifier and summarises "
            "occupancies, flagging structures that refine more than one "
            "conformer for a residue."
        ),
        "category": "Structure",
        "icon": "Layers",
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
        altloc_dim = str(params.get("altloc_dim", "altloc"))
        out_name = str(params.get("output", "altlocs"))

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_altloc_inventory: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        rows, summary = altloc_rows(form, atom_dim, field_dim)
        data = np.asarray(
            [
                [
                    row["n_atoms"],
                    row["n_residues"],
                    row["min_occupancy"],
                    row["max_occupancy"],
                    row["mean_occupancy"],
                ]
                for row in rows
            ],
            dtype=np.float32,
        ).reshape(len(rows), 5)
        out = Form(
            data=data,
            dims=[altloc_dim, "statistic"],
            labels={
                altloc_dim: {row["altloc"]: index for index, row in enumerate(rows)},
                "statistic": dict(_STATISTIC),
            },
            info={**summary, "note": "blank altloc is reported as '_'"},
        )
        out.validate()
        self._export_data = {
            "n_altlocs": len(rows),
            "n_altloc_atoms": summary["n_altloc_atoms"],
            "n_residues_with_alternates": summary["n_residues_with_alternates"],
            "altlocs": summary["altlocs"],
        }
        ctx[out_name] = out
        print(
            f"[structure_altloc_inventory] {len(rows)} conformers, "
            f"{summary['n_altloc_atoms']} altloc atoms, "
            f"{summary['n_residues_with_alternates']} residues with alternates"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
