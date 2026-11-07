"""Cis peptide bonds from backbone omega dihedrals.

Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``.
Output: 2D Form ``[bond, statistic]`` with ``omega``, ``abs_omega`` and an
``is_cis`` flag for every consecutive peptide bond of each chain.

A bond is classified as cis when ``abs(omega) <= cis_threshold`` degrees
(default 30).  Bonds that span a residue-numbering gap carry no peptide bond
and are skipped.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._structure_checks import chain_sequences, clean_residues, polymer_residues
from .structure_phi_psi import dihedral

_STATISTIC = {"omega": 0, "abs_omega": 1, "is_cis": 2}


def cis_peptide_rows(residues: list[dict], threshold: float) -> tuple[list[dict], int]:
    """Return one row per peptide bond plus the number of skipped pairs."""
    rows: list[dict] = []
    skipped = 0
    for chain, sequence in chain_sequences(residues).items():
        for previous, following in zip(sequence, sequence[1:]):
            if following["number"] - previous["number"] != 1:
                skipped += 1
                continue
            if not all(key in previous["coords"] for key in ("CA", "C")) or not all(
                key in following["coords"] for key in ("N", "CA")
            ):
                skipped += 1
                continue
            omega = dihedral(
                previous["coords"]["CA"],
                previous["coords"]["C"],
                following["coords"]["N"],
                following["coords"]["CA"],
            )
            if not np.isfinite(omega):
                skipped += 1
                continue
            rows.append(
                {
                    "label": f"{chain}:{previous['number']}-{following['number']}",
                    "chain": chain,
                    "omega": omega,
                    "abs_omega": abs(omega),
                    "is_cis": 1.0 if abs(omega) <= threshold else 0.0,
                }
            )
    return rows, skipped


class StructureCisPeptidesStep(Step):
    """Measure omega dihedrals and flag cis peptide bonds."""

    provider = "operon-core"
    parameters_file = "structure_cis_peptides.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_cis_peptides",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Cis peptide bonds from omega dihedrals",
        "description": (
            "Computes the backbone omega dihedral of every consecutive peptide "
            "bond and flags bonds whose absolute angle is below the cis "
            "threshold. Bonds across missing-residue gaps are skipped."
        ),
        "category": "Structure",
        "icon": "Compass",
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
        bond_dim = str(params.get("bond_dim", "bond"))
        out_name = str(params.get("output", "cis_peptides"))
        threshold = float(params.get("cis_threshold", 30.0))
        if not 0.0 <= threshold <= 90.0:
            raise StepError(
                "structure_cis_peptides: cis_threshold must be between 0 and 90 degrees"
            )
        chain = str(params.get("chain", "")).strip()

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_cis_peptides: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        residues = polymer_residues(form, atom_dim, field_dim)
        if not residues:
            raise StepError(
                "structure_cis_peptides: no polymer residues with a CA atom were found"
            )
        residues = clean_residues(residues, chain, "structure_cis_peptides")
        rows, skipped = cis_peptide_rows(residues, threshold)

        data = np.asarray(
            [[row["omega"], row["abs_omega"], row["is_cis"]] for row in rows],
            dtype=np.float32,
        ).reshape(len(rows), 3)
        cis_bonds = [row["label"] for row in rows if row["is_cis"] > 0.5]
        out = Form(
            data=data,
            dims=[bond_dim, "statistic"],
            labels={
                bond_dim: {row["label"]: index for index, row in enumerate(rows)},
                "statistic": dict(_STATISTIC),
            },
            info={
                "n_bonds": len(rows),
                "n_cis": len(cis_bonds),
                "cis_bonds": cis_bonds,
                "cis_threshold": threshold,
                "n_skipped": skipped,
                "note": "Bonds across missing-residue gaps and without backbone atoms are skipped",
            },
        )
        out.validate()
        self._export_data = {
            "n_bonds": len(rows),
            "n_cis": len(cis_bonds),
            "cis_bonds": cis_bonds,
            "cis_threshold": threshold,
            "n_skipped": skipped,
        }
        ctx[out_name] = out
        print(
            f"[structure_cis_peptides] {len(rows)} bonds, {len(cis_bonds)} cis "
            f"(|omega| <= {threshold:g}), {skipped} skipped"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
