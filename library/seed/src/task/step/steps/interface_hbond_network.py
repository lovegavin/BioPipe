"""Cross-chain hydrogen bond network at a protein-protein interface."""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.structure_hbonds import (
    _residues,
    hbond_energy,
    hydrogen_positions,
)


def interface_bonds(
    residues: list[dict],
    bonds_binder: set[str],
    bonds_target: set[str],
    energy_threshold: float = -0.5,
    max_distance: float = 5.2,
) -> list[dict]:
    """Return cross-chain backbone hydrogen bonds sorted by energy."""
    hydrogens = hydrogen_positions(residues)
    found: dict[tuple, dict] = {}
    for donor_index, donor in enumerate(residues):
        hydrogen = hydrogens[donor_index]
        if hydrogen is None or donor["resname"] == "PRO":
            continue
        donor_side = (
            "binder"
            if donor["chain"] in bonds_binder
            else "target" if donor["chain"] in bonds_target else ""
        )
        if not donor_side:
            continue
        for acceptor_index, acceptor in enumerate(residues):
            if acceptor_index == donor_index:
                continue
            acceptor_side = (
                "binder"
                if acceptor["chain"] in bonds_binder
                else "target" if acceptor["chain"] in bonds_target else ""
            )
            if not acceptor_side or acceptor_side == donor_side:
                continue
            distance = float(
                np.linalg.norm(acceptor["coords"]["O"] - donor["coords"]["N"])
            )
            if distance > max_distance:
                continue
            energy = hbond_energy(donor, acceptor, hydrogen)
            if not math.isfinite(energy) or energy >= energy_threshold:
                continue
            key = (donor["label"], acceptor["label"])
            best = found.get(key)
            if best is None or energy < best["energy"]:
                found[key] = {
                    "donor": donor["label"],
                    "acceptor": acceptor["label"],
                    "energy": float(energy),
                    "distance": distance,
                }
    rows = list(found.values())
    rows.sort(key=lambda row: (row["energy"], row["donor"], row["acceptor"]))
    return rows


class InterfaceHbondNetworkStep(Step):
    """Kabsch-Sander hydrogen bonds across a binder/target interface."""

    provider = "operon-core"
    parameters_file = "interface_hbond_network.InterfaceHbondNetworkStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_hbond_network",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface hydrogen bond network",
        "category": "Machine Learning",
        "icon": "Unite",
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
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Detect backbone hydrogen bonds between two chain groups with the "
            "Kabsch-Sander energy model and report energy and N-O distance."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom") or "atom")
        field_dim = str(params.get("field_dim", "field") or "field")
        bond_dim = str(params.get("bond_dim", "bond") or "bond")
        binder_text = str(params.get("binder_chains", "A") or "")
        target_text = str(params.get("target_chains", "") or "")
        energy_threshold = float(params.get("energy_threshold", -0.5))
        max_distance = float(params.get("max_distance", 5.2))
        out_name = params.get("output", self.name)

        if energy_threshold >= 0:
            raise StepError(
                "interface_hbond_network: energy_threshold must be negative"
            )
        if not 1.5 <= max_distance <= 10.0:
            raise StepError(
                "interface_hbond_network: max_distance must be between 1.5 and "
                "10.0 angstrom"
            )
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "interface_hbond_network: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        from src.task.step.steps._protein_common import decode_column

        labels = {str(value) for value in decode_column(form, field_dim, "chain")}
        binder_chains, target_chains = pick_chain_sides(
            labels, binder_text, target_text, "interface_hbond_network"
        )
        binder = set(binder_chains)
        target = set(target_chains)

        residues = _residues(form, atom_dim, field_dim)
        if len(residues) < 3:
            raise StepError(
                "interface_hbond_network: at least three residues with N, C and "
                "O atoms are required"
            )
        rows = interface_bonds(
            residues,
            binder,
            target,
            energy_threshold=energy_threshold,
            max_distance=max_distance,
        )

        data = np.asarray(
            [[row["energy"], row["distance"]] for row in rows], dtype=np.float32
        ).reshape(len(rows), 2)
        out = Form(
            data=data,
            dims=[bond_dim, "statistic"],
            labels={
                bond_dim: {
                    f"{row['donor']}->{row['acceptor']}": position
                    for position, row in enumerate(rows)
                },
                "statistic": {"energy": 0, "distance": 1},
            },
            info={
                "missing_code": np.nan,
                "bonds": [
                    {
                        "donor": row["donor"],
                        "acceptor": row["acceptor"],
                        "energy": round(row["energy"], 4),
                        "distance": round(row["distance"], 4),
                    }
                    for row in rows
                ],
                "n_bonds": len(rows),
                "binder_chains": binder_chains,
                "target_chains": target_chains,
                "energy_threshold": energy_threshold,
                "max_distance": max_distance,
                "unit": "kcal/mol",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_bonds": len(rows),
            "binder_chains": binder_chains,
            "target_chains": target_chains,
            "strongest": round(float(data[0, 0]), 4) if len(rows) else None,
        }
        print(
            f"[interface_hbond_network] {len(rows)} interface bond(s) between "
            f"{binder_chains} and {target_chains}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
