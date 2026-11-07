"""ligand_pdbqt_flexible: flexible-ligand PDBQT with a torsion tree."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.ligand_pdbqt_prepare import ad4_type, prepare_molecule
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_ROTATABLE = "[!$(*#*)&!D1]-&!@[!$(*#*)&!D1]"
_AMIDE = "[NX3][CX3](=[OX1])"


def rotatable_bonds(molecule) -> list[tuple[int, int]]:
    """Return the acyclic single bonds treated as ligand torsions."""

    from rdkit import Chem

    amide = Chem.MolFromSmarts(_AMIDE)
    amide_atoms = set()
    for match in molecule.GetSubstructMatches(amide):
        amide_atoms.update(match)
    heavy_degree = {
        atom.GetIdx(): sum(1 for neighbour in atom.GetNeighbors() if neighbour.GetAtomicNum() > 1)
        for atom in molecule.GetAtoms()
    }
    bonds = []
    for bond in molecule.GetBonds():
        first, second = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if bond.GetBondType() != Chem.BondType.SINGLE or bond.IsInRing():
            continue
        if bond.GetBeginAtom().GetAtomicNum() <= 1 or bond.GetEndAtom().GetAtomicNum() <= 1:
            continue
        if heavy_degree[first] < 2 or heavy_degree[second] < 2:
            continue
        if first in amide_atoms and second in amide_atoms:
            continue
        bonds.append((first, second))
    return bonds


def torsion_tree(molecule) -> list[str]:
    """Render the ligand as a PDBQT torsion tree (ROOT ... ENDROOT, BRANCH/ENDBRANCH)."""

    from rdkit import Chem

    conformer = molecule.GetConformer()
    heavy = [atom.GetIdx() for atom in molecule.GetAtoms() if atom.GetAtomicNum() > 1]
    if not heavy:
        raise StepError("ligand_pdbqt_flexible: the molecule carries no heavy atom")
    rotatable = {tuple(sorted(pair)) for pair in rotatable_bonds(molecule)}
    adjacency: dict[int, list[int]] = {index: [] for index in heavy}
    for bond in molecule.GetBonds():
        first, second = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if first in adjacency and second in adjacency:
            adjacency[first].append(second)
            adjacency[second].append(first)

    serial_of: dict[int, int] = {}
    counter = [0]

    def atom_line(index: int, serial: int) -> str:
        atom = molecule.GetAtomWithIdx(index)
        position = conformer.GetAtomPosition(index)
        charge = float(atom.GetProp("_GasteigerCharge")) if atom.HasProp("_GasteigerCharge") else 0.0
        if not np.isfinite(charge):
            charge = 0.0
        label = atom.GetSymbol() + str(index + 1)
        return (
            "ATOM  {serial:5d} {label:<4s} LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    "
            "{charge:7.3f} {atype:<2s}".format(
                serial=serial,
                label=label,
                x=position.x,
                y=position.y,
                z=position.z,
                charge=charge,
                atype=ad4_type(atom),
            )
        )

    lines: list[str] = ["ROOT"]

    def emit_component(start: int) -> None:
        """Emit one rigid fragment (connected through non-rotatable bonds)."""

        stack = [start]
        while stack:
            index = stack.pop()
            if index in serial_of:
                continue
            counter[0] += 1
            serial_of[index] = counter[0]
            lines.append(atom_line(index, counter[0]))
            for neighbour in adjacency[index]:
                if neighbour in serial_of:
                    continue
                if tuple(sorted((index, neighbour))) in rotatable:
                    continue
                stack.append(neighbour)

    def collect_component(start: int) -> list[int]:
        atoms = []
        stack = [start]
        while stack:
            index = stack.pop()
            if index in atoms:
                continue
            atoms.append(index)
            for neighbour in adjacency[index]:
                if neighbour in atoms:
                    continue
                if tuple(sorted((index, neighbour))) in rotatable:
                    continue
                stack.append(neighbour)
        return atoms

    def emit_branches(component: list[int]) -> None:
        for index in component:
            for neighbour in adjacency[index]:
                if tuple(sorted((index, neighbour))) not in rotatable:
                    continue
                if neighbour in serial_of:
                    continue
                parent_serial = serial_of[index]
                child_serial = counter[0] + 1
                lines.append(f"BRANCH {parent_serial:3d} {child_serial:3d}")
                emit_component(neighbour)
                emit_branches(collect_component(neighbour))
                lines.append(f"ENDBRANCH {parent_serial:3d} {child_serial:3d}")

    emit_component(heavy[0])
    lines.append("ENDROOT")
    emit_branches(list(serial_of))
    lines.append(f"TORSDOF {len(rotatable)}")
    return lines


def prepare_flexible(smiles: str, *, seed: int = 0, optimize: bool = True):
    """Build a 3D molecule and return its PDBQT lines plus torsion metadata."""

    molecule = prepare_molecule(smiles, seed=seed, optimize=optimize)
    lines = torsion_tree(molecule)
    from rdkit import Chem

    count = len(rotatable_bonds(molecule))
    reference = int(Chem.rdMolDescriptors.CalcNumRotatableBonds(molecule))
    return {"lines": lines, "torsions": count, "rdkit_torsions": reference, "molecule": molecule}


class LigandPdbqtFlexibleStep(Step):
    provider = "operon-core"
    parameters_file = "ligand_pdbqt_flexible.LigandPdbqtFlexibleStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "ligand_pdbqt_flexible",
        "version": "1.0.0",
        "kind": "operator",
        "title": "柔性配体 PDBQT 准备（扭转树）",
        "description": (
            "Convert SMILES into a flexible AutoDock PDBQT ligand: build a 3D conformer "
            "with RDKit, emit a ROOT/BRANCH/ENDBRANCH torsion tree and set TORSDOF from "
            "the rotatable single bonds."
        ),
        "category": "Docking",
        "icon": "Flask",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["rdkit>=2023.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        smiles = str(params.get("smiles", "")).strip()
        if not smiles:
            raise StepError("ligand_pdbqt_flexible: smiles is required")
        result = prepare_flexible(smiles, seed=int(params.get("seed", 0)), optimize=bool(params.get("optimize", True)))
        directory = output_directory(ctx, "ligand_pdbqt_flexible")
        native_path = directory / "ligand.pdbqt"
        native_path.write_text("\n".join(result["lines"]) + "\n", encoding="utf-8")
        path_text = str(params.get("output_path", "")).strip()
        if path_text:
            path = Path(path_text).expanduser()
            if path.suffix.lower() != ".pdbqt":
                raise StepError("ligand_pdbqt_flexible: output_path must end with .pdbqt")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(result["lines"]) + "\n")
        molecule = result["molecule"]
        values = np.asarray([[result["torsions"], result["rdkit_torsions"], molecule.GetNumHeavyAtoms()]], dtype=np.float32)
        out_dim = str(params.get("atom_dim", "ligand"))
        out_name = str(params.get("output", "ligand"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {"ligand": 0},
                "statistic": {"torsions": 0, "rdkit_torsions": 1, "heavy_atoms": 2},
            },
            info={
                "missing_code": np.nan,
                "smiles": smiles,
                "n_torsions": result["torsions"],
                "rdkit_num_rotatable_bonds": result["rdkit_torsions"],
                "n_atoms": int(molecule.GetNumAtoms()),
                "output_path": path_text,
                "native_path": str(native_path),
                "pdbqt": result["lines"],
            },
        )
        result_files = [result_file("ligand", native_path, "pdbqt", "Flexible ligand")]
        remember_native(ctx, out_name, result_files)
        self._export_data = {
            "n_torsions": result["torsions"],
            "rdkit_num_rotatable_bonds": result["rdkit_torsions"],
            "output_path": path_text,
            "result_files": result_files,
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
