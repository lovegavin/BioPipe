"""Interface-driven masked ProteinMPNN design.

The interface of a binder/target complex is derived from heavy-atom contacts,
and only the interface residues of the selected side are redesigned (every other
residue stays fixed).  This removes hand-written residue masks from interface
optimisation workflows while keeping the official ProteinMPNN runner.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    contact_stats,
    decode_column,
    heavy_atom_mask,
    residue_labels,
    split_chains,
)
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.proteinmpnn_design import pdb_chains
from src.task.step.steps.proteinmpnn_interface_redesign import _THREE_TO_ONE
from src.task.step.steps.proteinmpnn_masked_design import mask_payload, run_masked_designer

_STATISTICS = ("score", "global_score")


def _protein_hits(hits: set[str], side: str) -> set[str]:
    """Drop water, ion and ligand rows before they reach the protein mask."""

    kept = {label for label in hits if label.split(":")[1] in _THREE_TO_ONE}
    if not kept:
        raise StepError(
            "proteinmpnn_masked_interface_design: no protein residue was found on the "
            f"{side} side of the interface"
        )
    return kept

_SIDES = ("binder", "target", "both")


def interface_residues(
    coords: np.ndarray,
    labels: np.ndarray,
    chains: np.ndarray,
    binder: list[str],
    target: list[str],
    cutoff: float,
) -> tuple[set[str], set[str], int]:
    """Interface residue labels on both sides plus the contact pair count."""

    binder_mask = np.isin(chains, binder)
    target_mask = np.isin(chains, target)
    if not binder_mask.any() or not target_mask.any():
        raise StepError(
            "proteinmpnn_masked_interface_design: both chain groups need heavy atoms"
        )
    binder_coords = coords[binder_mask]
    target_coords = coords[target_mask]
    binder_counts, _ = contact_stats(binder_coords, target_coords, cutoff)
    target_counts, _ = contact_stats(target_coords, binder_coords, cutoff)
    binder_hits = {str(label) for label in labels[binder_mask][binder_counts > 0]}
    target_hits = {str(label) for label in labels[target_mask][target_counts > 0]}
    pairs = int(binder_counts.sum())
    return binder_hits, target_hits, pairs


def mask_from_labels(labels: set[str]) -> dict[str, list[int]]:
    """``{chain: [author residue numbers]}`` from ``chain:resname:number`` labels."""

    mask: dict[str, list[int]] = {}
    for label in labels:
        parts = str(label).split(":")
        if len(parts) < 3:
            raise StepError(
                f"proteinmpnn_masked_interface_design: unexpected residue label '{label}'"
            )
        chain = parts[0]
        number = parts[-1]
        try:
            value = int(float(number))
        except ValueError as error:
            raise StepError(
                "proteinmpnn_masked_interface_design: insertion-coded or "
                f"non-numeric residue '{label}' cannot be mapped to ProteinMPNN"
            ) from error
        mask.setdefault(chain, []).append(value)
    return {chain: sorted(set(numbers)) for chain, numbers in mask.items()}


class ProteinmpnnMaskedInterfaceDesignStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_masked_interface_design."
        "ProteinmpnnMaskedInterfaceDesignStep.parameters.json"
    )

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_masked_interface_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface-masked ProteinMPNN design",
        "description": (
            "Redesign the interface residues of a binder/target complex with "
            "official ProteinMPNN; the interface mask is derived from heavy-atom "
            "contacts instead of a residue list."
        ),
        "category": "Machine Learning",
        "icon": "Intersect",
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
                    "info": {"encoders": {"type": "object", "optional": True}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError(
                "proteinmpnn_masked_interface_design: a PDB atom form input is required"
            )
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        design_dim = str(params.get("design_dim") or "design")
        out_name = str(params.get("output") or "designs")

        structure_text = str(params.get("structure_path") or "").strip()
        if not structure_text:
            raise StepError(
                "proteinmpnn_masked_interface_design: structure_path is required "
                "(the PDB file the atom form was read from)"
            )
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(
                f"proteinmpnn_masked_interface_design: structure_path '{structure}' is not a file"
            )
        if structure.suffix.lower() != ".pdb":
            raise StepError(
                "proteinmpnn_masked_interface_design: structure_path must be a .pdb file"
            )

        cutoff = float(params.get("cutoff") if params.get("cutoff") is not None else 4.5)
        if not 0.0 < cutoff <= 10.0:
            raise StepError("proteinmpnn_masked_interface_design: cutoff must be in (0, 10]")
        side = str(params.get("mask_side") or "binder").strip().lower()
        if side not in _SIDES:
            raise StepError(
                f"proteinmpnn_masked_interface_design: mask_side must be one of {list(_SIDES)}"
            )

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "proteinmpnn_masked_interface_design: expected a PDB atom table with dims "
                f"[{atom_dim}, {field_dim}], got {list(form.dims)}"
            )
        heavy = heavy_atom_mask(form, field_dim)
        if not heavy.any():
            raise StepError(
                "proteinmpnn_masked_interface_design: the structure form has no heavy atoms"
            )
        xyz = np.column_stack(
            [
                np.asarray(form.data[heavy, column_index(form, field_dim, axis)], dtype=np.float64)
                for axis in ("x", "y", "z")
            ]
        )
        chain_column = decode_column(form, field_dim, "chain")
        if chain_column is None:
            raise StepError(
                "proteinmpnn_masked_interface_design: the structure form has no 'chain' column"
            )
        chains = np.asarray(chain_column, dtype=object)[heavy]
        labels = residue_labels(form, field_dim)[heavy]

        present = sorted({str(chain) for chain in chains})
        binder, target = pick_chain_sides(
            set(present),
            params.get("binder_chains", ""),
            params.get("target_chains", ""),
            "proteinmpnn_masked_interface_design",
        )
        binder_hits, target_hits, pairs = interface_residues(
            xyz, labels, chains, binder, target, cutoff
        )
        if not binder_hits or not target_hits:
            raise StepError(
                "proteinmpnn_masked_interface_design: no heavy-atom contact was found "
                f"between {binder} and {target} at {cutoff} A"
            )
        binder_hits = _protein_hits(binder_hits, "binder")
        target_hits = _protein_hits(target_hits, "target")

        if side == "binder":
            interface = binder_hits
            side_chains = binder
        elif side == "target":
            interface = target_hits
            side_chains = target
        else:
            interface = binder_hits | target_hits
            side_chains = binder + target

        mask = mask_from_labels(interface)
        file_chains = pdb_chains(structure)
        missing = sorted(set(mask) - set(file_chains))
        if missing:
            raise StepError(
                "proteinmpnn_masked_interface_design: chain(s) "
                + ", ".join(missing)
                + " of the interface form are not present in "
                f"{structure.name}"
            )
        unknown = [
            f"{chain}:{number}"
            for chain, numbers in mask.items()
            for number in numbers
            if number not in file_chains[chain]
        ]
        if unknown:
            raise StepError(
                "proteinmpnn_masked_interface_design: interface residue(s) "
                + ", ".join(unknown[:5])
                + " are not author residue numbers of the structure file"
            )

        design_chains = split_chains(params.get("chains", "")) or sorted(side_chains)
        invalid = sorted(set(design_chains) - set(mask))
        if invalid:
            raise StepError(
                "proteinmpnn_masked_interface_design: chain(s) "
                + ", ".join(invalid)
                + " carry no interface residue on mask_side="
                + side
            )

        payload = mask_payload(mask, file_chains, structure.stem)
        try:
            designs = run_masked_designer(
                params, structure, " ".join(design_chains), payload
            )
        except StepError as error:
            message = str(error)
            if message.startswith("proteinmpnn_masked_design:"):
                message = "proteinmpnn_masked_interface_design:" + message.split(":", 1)[1]
            raise StepError(message) from error
        if not designs:
            raise StepError(
                "proteinmpnn_masked_interface_design: ProteinMPNN returned no designs"
            )

        sequences = [record["sequence"] for record in designs]
        data = np.asarray(
            [[record["score"], record["global_score"]] for record in designs],
            dtype=np.float32,
        )
        out = Form(
            data=data,
            dims=[design_dim, "statistic"],
            labels={
                design_dim: {f"design{index + 1}": index for index in range(len(designs))},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequences": sequences,
                "n_designs": len(designs),
                "interface_residues": {chain: list(numbers) for chain, numbers in mask.items()},
                "n_interface_residues": int(sum(len(numbers) for numbers in mask.values())),
                "mask_side": side,
                "binder_chains": binder,
                "target_chains": target,
                "design_chains": design_chains,
                "cutoff": cutoff,
                "n_contact_pairs": pairs,
                "fixed_positions": payload[structure.stem],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(designs),
            "n_interface_residues": sum(len(numbers) for numbers in mask.values()),
            "mask_side": side,
            "n_contact_pairs": pairs,
        }
        print(
            f"[proteinmpnn_masked_interface_design] {len(designs)} designs, "
            f"{len(interface)} interface residues on chains {design_chains}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
