"""structure_pdbqt_flexible_receptor: rigid + flexible-residue PDBQT pair."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column
from src.task.step.steps.vina_dock_python import ad4_type
from src.task.step.steps._native_results import output_directory, remember_native, result_file

BACKBONE = {"N", "CA", "C", "O", "OXT"}


def _residue_key(chain: str, number: int) -> str:
    return f"{chain}:{int(number)}"


def residue_groups(form: Form, field_dim: str) -> dict[tuple[str, int], dict]:
    """Group heavy atoms by residue."""

    names = decode_column(form, field_dim, "atom_name")
    resnames = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    numbers = decode_column(form, field_dim, "residue_number")
    elements = decode_column(form, field_dim, "element")
    groups: dict[tuple[str, int], dict] = {}
    for row in range(form.data.shape[0]):
        element = str(elements[row]).strip()
        if element.upper() == "H":
            continue
        key = (str(chains[row]), int(float(numbers[row])))
        group = groups.setdefault(key, {"resname": str(resnames[row]), "atoms": []})
        group["atoms"].append(
            {
                "name": str(names[row]),
                "element": element,
                "coords": np.asarray(form.data[row, :3], dtype=float),
            }
        )
    return groups


def _side_chain(group: dict) -> list[dict]:
    return [atom for atom in group["atoms"] if atom["name"].upper() not in BACKBONE]


def _atom_line(atom: dict, serial: int, resname: str, chain: str, number: int) -> str:
    x, y, z = atom["coords"]
    return (
        f"ATOM  {serial:5d} {atom['name'][:4]:<4s} {resname[:3]:>3s} {chain[:1]}{int(number):4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 {ad4_type(atom['element']):<2s}"
    )


def _degrees(atoms: list[dict], context: list[dict]) -> list[int]:
    degrees = []
    for atom in atoms:
        count = 0
        for other in context:
            if other is atom:
                continue
            if float(np.linalg.norm(atom["coords"] - other["coords"])) < 1.9:
                count += 1
        degrees.append(count)
    return degrees


def _rotatable(atoms: list[dict], context: list[dict] | None = None) -> list[tuple[int, int]]:
    context = context if context is not None else atoms
    degrees = _degrees(atoms, context)
    bonds = []
    for first in range(len(atoms)):
        for second in range(first + 1, len(atoms)):
            distance = float(np.linalg.norm(atoms[first]["coords"] - atoms[second]["coords"]))
            if distance >= 1.9:
                continue
            if degrees[first] < 2 or degrees[second] < 2:
                continue
            bonds.append((first, second))
    return bonds


def flexible_residues(form: Form, field_dim: str, selection: str = "") -> list[tuple[str, int]]:
    """Return the flexible residue keys, or the candidates with side chains."""

    groups = residue_groups(form, field_dim)
    candidates = [
        key
        for key, group in sorted(groups.items())
        if any(atom["name"].upper() == "CB" for atom in group["atoms"])
        and len(_side_chain(group)) > 1
    ]
    if not selection.strip():
        return candidates
    chosen = []
    for token in selection.replace(";", ",").split(","):
        text = token.strip()
        if not text:
            continue
        if ":" not in text:
            raise StepError(f"structure_pdbqt_flexible_receptor: '{text}' is not of the form A:45")
        chain, number = text.split(":", 1)
        try:
            key = (chain.strip(), int(number))
        except ValueError as exc:
            raise StepError(f"structure_pdbqt_flexible_receptor: '{text}' is not of the form A:45") from exc
        if key not in groups:
            raise StepError(f"structure_pdbqt_flexible_receptor: residue {text} is not in the structure")
        if key not in candidates:
            raise StepError(f"structure_pdbqt_flexible_receptor: residue {text} has no flexible side chain")
        chosen.append(key)
    if not chosen:
        raise StepError("structure_pdbqt_flexible_receptor: no flexible residue was requested")
    return chosen


def build_pair(form: Form, field_dim: str, selected: list[tuple[str, int]], *, probe: float = 1.9) -> dict:
    """Split the structure into a rigid PDBQT and BEGIN_RES flex blocks."""

    groups = residue_groups(form, field_dim)
    flex_atoms = {key: _side_chain(groups[key]) for key in selected}
    rigid_lines = []
    serial = 0
    for key, group in sorted(groups.items()):
        chain, number = key
        drop = {id(atom) for atom in flex_atoms.get(key, [])}
        for atom in group["atoms"]:
            if id(atom) in drop:
                continue
            serial += 1
            rigid_lines.append(_atom_line(atom, serial, group["resname"], chain, number))
    rigid_lines.append("END")
    flex_lines = []
    for key in selected:
        chain, number = key
        resname = groups[key]["resname"]
        atoms = flex_atoms[key]
        names = [atom["name"] for atom in atoms]
        if "CB" not in names:
            raise StepError(f"structure_pdbqt_flexible_receptor: residue {_residue_key(chain, number)} has no CB atom")
        root_index = names.index("CB")
        bonds = _rotatable(atoms, group["atoms"])
        adjacency: dict[int, list[int]] = {index: [] for index in range(len(atoms))}
        for first, second in bonds:
            adjacency[first].append(second)
            adjacency[second].append(first)
        serial_of: dict[int, int] = {}
        counter = [serial]

        def emit_line(index: int) -> None:
            counter[0] += 1
            serial_of[index] = counter[0]
            flex_lines.append(_atom_line(atoms[index], counter[0], resname, chain, number))

        def emit_component(start: int) -> None:
            stack = [start]
            while stack:
                index = stack.pop()
                if index in serial_of:
                    continue
                emit_line(index)
                for neighbour in adjacency[index]:
                    if neighbour in serial_of or tuple(sorted((index, neighbour))) in {
                        tuple(sorted(pair)) for pair in bonds
                    }:
                        continue
                    stack.append(neighbour)

        def emit_branches(component: list[int]) -> None:
            for index in component:
                for neighbour in adjacency[index]:
                    if tuple(sorted((index, neighbour))) not in {tuple(sorted(pair)) for pair in bonds}:
                        continue
                    if neighbour in serial_of:
                        continue
                    parent = serial_of[index]
                    child = counter[0] + 1
                    flex_lines.append(f"BRANCH {parent:3d} {child:3d}")
                    emit_component(neighbour)
                    child_component = [neighbour]
                    emit_branches(child_component)
                    flex_lines.append(f"ENDBRANCH {parent:3d} {child:3d}")

        flex_lines.append(f"BEGIN_RES {resname[:3]:>3s} {chain[:1]} {int(number):4d}")
        flex_lines.append("ROOT")
        emit_line(root_index)
        flex_lines.append("ENDROOT")
        component = [root_index]
        emit_branches(component)
        flex_lines.append("END_RES")
        serial = counter[0]
    return {
        "rigid": "\n".join(rigid_lines) + "\n",
        "flex": "\n".join(flex_lines) + "\n",
        "n_rigid_atoms": len(rigid_lines) - 1,
        "n_flex_atoms": sum(len(atoms) for atoms in flex_atoms.values()),
        "n_flex_residues": len(selected),
        "n_torsions": sum(1 + len(_rotatable(atoms, groups[key]["atoms"])) for key, atoms in flex_atoms.items()),
        "residues": [_residue_key(chain, number) for chain, number in selected],
    }


class StructurePdbqtFlexibleReceptorStep(Step):
    provider = "operon-core"
    parameters_file = "structure_pdbqt_flexible_receptor.StructurePdbqtFlexibleReceptorStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_pdbqt_flexible_receptor",
        "version": "1.0.0",
        "kind": "operator",
        "title": "柔性受体 PDBQT（刚性 + 柔性残基）",
        "description": (
            "Split a protein structure into a rigid PDBQT receptor and a flexible-residue "
            "PDBQT file with BEGIN_RES blocks, so AutoDock Vina can sample selected side-chain "
            "torsions during docking."
        ),
        "category": "Docking",
        "icon": "ShareNetwork",
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
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_pdbqt_flexible_receptor: the structure form is empty")
        field_dim = str(params.get("field_dim", "field"))
        selected = flexible_residues(form, field_dim, str(params.get("flexible_residues", "")))
        if not selected:
            raise StepError("structure_pdbqt_flexible_receptor: no residue carries a flexible side chain")
        result = build_pair(form, field_dim, selected)
        directory = output_directory(ctx, "pdbqt_receptor")
        native_rigid = directory / "receptor.pdbqt"
        native_flex = directory / "flex.pdbqt"
        native_rigid.write_text(result["rigid"])
        native_flex.write_text(result["flex"])
        rigid_path = str(params.get("output_path", "")).strip()
        flex_path = str(params.get("flex_output_path", "")).strip()
        if rigid_path:
            path = Path(rigid_path).expanduser()
            if path.suffix.lower() != ".pdbqt":
                raise StepError("structure_pdbqt_flexible_receptor: output_path must end with .pdbqt")
            path.write_text(result["rigid"])
        if flex_path:
            path = Path(flex_path).expanduser()
            if path.suffix.lower() != ".pdbqt":
                raise StepError("structure_pdbqt_flexible_receptor: flex_output_path must end with .pdbqt")
            path.write_text(result["flex"])
        values = np.asarray([[result["n_flex_residues"], result["n_flex_atoms"], result["n_torsions"]]], dtype=np.float32)
        out_dim = str(params.get("residue_dim", "receptor"))
        out_name = str(params.get("output", "receptor"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {"receptor": 0},
                "statistic": {"n_flex_residues": 0, "n_flex_atoms": 1, "n_torsions": 2},
            },
            info={
                "missing_code": np.nan,
                "flexible_residues": result["residues"],
                "rigid_atoms": result["n_rigid_atoms"],
                "flex_atoms": result["n_flex_atoms"],
                "n_torsions": result["n_torsions"],
                "output_path": rigid_path,
                "native_rigid_path": str(native_rigid),
                "native_flex_path": str(native_flex),
                "flex_output_path": flex_path,
            },
        )
        result_files = [result_file("receptor", native_rigid, "pdbqt", "Rigid receptor"), result_file("flex", native_flex, "pdbqt", "Flexible receptor")]
        remember_native(ctx, out_name, result_files)
        self._export_data = {
            "result_files": result_files,
            "rigid": result["rigid"],
            "flex": result["flex"],
            "residues": result["residues"],
            "n_torsions": result["n_torsions"],
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
