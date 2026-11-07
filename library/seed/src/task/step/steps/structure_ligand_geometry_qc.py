"""structure_ligand_geometry_qc: PoseBusters-style ligand geometry checks."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, heavy_atom_mask

STATISTICS = (
    "n_atoms",
    "n_bonds",
    "n_bond_outliers",
    "max_bond_deviation",
    "n_clashes",
    "min_protein_distance",
)


def _rdkit():
    try:
        from rdkit import Chem
        from rdkit.Chem import rdDistGeom
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError("structure_ligand_geometry_qc: RDKit is required; install it with 'python -m pip install rdkit'") from exc
    return Chem, rdDistGeom


def ligand_block(form: Form, atom_dim: str, field_dim: str, resnames: set[str], *, protein_only: bool = False) -> tuple[str, list[int], np.ndarray]:
    """Select ligand (or protein) atoms and render them as a PDB block."""

    names = decode_column(form, field_dim, "resname")
    keep = np.asarray([str(name).strip().upper() in resnames for name in names])
    if protein_only:
        keep = ~keep
    if not keep.any():
        if protein_only:
            return "", [], np.zeros((0, 3), dtype=float)
        raise StepError(f"structure_ligand_geometry_qc: no atoms match residue names {sorted(resnames)}")
    columns = {name: form.data[:, index] for name, index in form.labels["field"].items()}
    lines = []
    for local, index in enumerate(np.where(keep)[0]):
        record = "HETATM" if not protein_only else "ATOM  "
        element = str(decode_column(form, field_dim, "element")[index]).strip().upper() or "C"
        name = str(decode_column(form, field_dim, "atom_name")[index]).strip()
        resname = str(names[index]).strip().upper()[:3]
        chain = str(decode_column(form, field_dim, "chain")[index]).strip()[:1] or "A"
        number = int(float(columns["residue_number"][index]))
        x, y, z = (float(columns[axis][index]) for axis in ("x", "y", "z"))
        lines.append(
            f"{record}{local + 1:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"
        )
    return "\n".join(lines) + "\nEND\n", list(np.where(keep)[0]), np.asarray([columns[axis][keep] for axis in ("x", "y", "z")], dtype=float).T


def bond_outliers(molecule, coordinates: np.ndarray, tolerance: float = 0.05) -> tuple[list[dict], float]:
    """Compare measured bond lengths against RDKit distance-geometry bounds."""

    Chem, _rdDistGeom = _rdkit()
    table = Chem.GetPeriodicTable()
    rows = []
    worst = 0.0
    for bond in molecule.GetBonds():
        first = bond.GetBeginAtomIdx()
        second = bond.GetEndAtomIdx()
        measured = float(np.linalg.norm(coordinates[first] - coordinates[second]))
        radius_sum = table.GetRcovalent(molecule.GetAtomWithIdx(first).GetAtomicNum()) + table.GetRcovalent(
            molecule.GetAtomWithIdx(second).GetAtomicNum()
        )
        lower = 0.6 * radius_sum
        upper = 1.3 * radius_sum
        deviation = 0.0
        if measured < lower:
            deviation = lower - measured
        elif measured > upper:
            deviation = measured - upper
        worst = max(worst, deviation)
        if deviation > tolerance:
            rows.append({"first": first, "second": second, "measured": measured, "lower": lower, "upper": upper, "deviation": deviation})
    return rows, worst


def clash_summary(ligand: np.ndarray, protein: np.ndarray, cutoff: float = 2.0) -> tuple[int, float]:
    """Count protein-ligand heavy-atom contacts below the clash cutoff."""

    if protein.size == 0 or ligand.size == 0:
        return 0, float("inf")
    from scipy.spatial import cKDTree

    tree = cKDTree(protein)
    distances, _ = tree.query(ligand, k=1)
    return int((distances < cutoff).sum()), float(distances.min())


class StructureLigandGeometryQcStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_geometry_qc.StructureLigandGeometryQcStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_geometry_qc",
        "version": "1.0.0",
        "kind": "operator",
        "title": "配体几何与碰撞质检",
        "description": (
            "Check a bound ligand against RDKit distance-geometry bounds for bond "
            "lengths and against the protein for steric clashes."
        ),
        "category": "Structure",
        "icon": "Cube",
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
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["rdkit"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_ligand_geometry_qc: the structure form is empty")
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        resnames = {name.strip().upper() for name in str(params.get("ligand_resname", "LIG")).split(",") if name.strip()}
        if not resnames:
            raise StepError("structure_ligand_geometry_qc: ligand_resname must list at least one residue name")
        Chem, _rdDistGeom = _rdkit()
        block, indices, coordinates = ligand_block(form, atom_dim, field_dim, resnames)
        molecule = Chem.MolFromPDBBlock(block, removeHs=False, sanitize=True)
        if molecule is None:
            raise StepError("structure_ligand_geometry_qc: RDKit could not perceive the ligand (check residue names and element columns)")
        Chem.SanitizeMol(molecule)
        outliers, worst = bond_outliers(molecule, coordinates, float(params.get("bond_tolerance", 0.05)))
        protein_block, _protein_indices, protein_coordinates = ligand_block(form, atom_dim, field_dim, resnames, protein_only=True)
        del protein_block
        clashes, minimum = clash_summary(coordinates, protein_coordinates, float(params.get("clash_cutoff", 2.0)))
        statistics = {
            "n_atoms": float(len(indices)),
            "n_bonds": float(molecule.GetNumBonds()),
            "n_bond_outliers": float(len(outliers)),
            "max_bond_deviation": worst,
            "n_clashes": float(clashes),
            "min_protein_distance": minimum if np.isfinite(minimum) else 0.0,
        }
        ligand_label = next(iter(resnames))
        output_dim = str(params.get("ligand_dim", "ligand"))
        out_name = str(params.get("output", "qc"))
        ctx[out_name] = Form(
            data=np.asarray([[statistics[name] for name in STATISTICS]], dtype=np.float32),
            dims=[output_dim, "statistic"],
            labels={output_dim: {ligand_label: 0}, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": np.nan,
                "ligand_resname": ligand_label,
                "outlier_bonds": outliers,
                "clash_cutoff": float(params.get("clash_cutoff", 2.0)),
            },
        )
        self._export_data = {"statistics": statistics, "outliers": outliers}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
