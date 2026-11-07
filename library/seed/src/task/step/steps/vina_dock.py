"""Molecular docking with the official AutoDock Vina command line."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_ATOMIC_NUMBER = {
    "H": 1, "C": 6, "N": 7, "O": 8, "F": 9, "P": 15, "S": 16,
    "CL": 17, "BR": 35, "I": 53, "ZN": 30, "FE": 26, "MG": 12, "CA": 20,
    "MN": 25, "CU": 29, "NA": 11, "K": 19, "SE": 34, "B": 5, "SI": 14,
}

_ELEMENT_ALIASES = {
    "A": "C", "C": "C", "N": "N", "NA": "N", "NS": "N", "OA": "O", "O": "O",
    "OS": "O", "S": "S", "SA": "S", "H": "H", "HD": "H", "HS": "H",
    "F": "F", "CL": "CL", "BR": "BR", "I": "I", "P": "P", "ZN": "ZN",
}


def element_of(atom_type: str, atom_name: str = "") -> str:
    """Map a PDBQT atom type (``A``, ``OA``, ``NA``, ``HD`` …) to an element."""

    cleaned = re.sub(r"[^A-Za-z]", "", atom_type or "").upper()
    if cleaned in _ELEMENT_ALIASES:
        return _ELEMENT_ALIASES[cleaned]
    if cleaned:
        two = cleaned[:2]
        if two in _ATOMIC_NUMBER:
            return two
        if cleaned[0] in _ATOMIC_NUMBER:
            return cleaned[0]
    name = re.sub(r"[^A-Za-z]", "", atom_name or "").upper()
    if name[:2] in _ATOMIC_NUMBER:
        return name[:2]
    return name[:1] or "C"


def parse_vina_log(text: str) -> dict:
    """Affinity table and RMSD bounds from a Vina log."""

    affinities: list[float] = []
    lower: list[float] = []
    upper: list[float] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0].isdigit():
            try:
                affinities.append(float(parts[1]))
                lower.append(float(parts[2]))
                upper.append(float(parts[3]))
            except ValueError:
                continue
    return {
        "affinities": affinities,
        "best_affinity": affinities[0] if affinities else float("nan"),
        "rmsd_lb": lower,
        "rmsd_ub": upper,
    }


def parse_poses(path: Path) -> list[dict]:
    """Parse the ``MODEL`` blocks of a Vina output PDBQT into poses."""

    poses: list[dict] = []
    current: dict | None = None
    serial = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip("\n")
        if line.startswith("MODEL"):
            current = {"atoms": []}
            poses.append(current)
            continue
        if line.startswith("ENDMDL"):
            current = None
            continue
        if not line.startswith(("ATOM", "HETATM")):
            continue
        serial += 1
        if current is None:
            current = {"atoms": []}
            poses.append(current)
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError as exc:
            raise StepError(f"vina_dock: malformed pose line {line!r}") from exc
        charge = 0.0
        for piece in line[70:].split():
            try:
                charge = float(piece)
                break
            except ValueError:
                continue
        atom_type = line[77:79].strip() or line[12:16].strip()[:1]
        element = element_of(atom_type, line[12:16].strip())
        current["atoms"].append(
            {
                "serial": serial,
                "x": x,
                "y": y,
                "z": z,
                "charge": charge,
                "element": element,
                "atom_name": line[12:16].strip() or element,
                "resname": line[17:20].strip() or "UNK",
            }
        )
    if not poses:
        raise StepError(f"vina_dock: '{path}' holds no MODEL blocks")
    for index, pose in enumerate(poses, start=1):
        pose["index"] = index
        pose["n_atoms"] = len(pose["atoms"])
        pose["coordinates"] = np.asarray(
            [[atom["x"], atom["y"], atom["z"]] for atom in pose["atoms"]],
            dtype=np.float64,
        )
        pose["elements"] = [atom["element"] for atom in pose["atoms"]]
        if pose["n_atoms"] == 0:
            raise StepError(f"vina_dock: pose {index} holds no atoms")
    return poses


def ligand_centroid(path: Path) -> tuple[float, float, float]:
    """Centroid of the first pose of a PDBQT/PFQ ligand file."""

    poses = parse_poses(path)
    return tuple(float(value) for value in poses[0]["coordinates"].mean(axis=0))


def docking_command(
    params: dict,
    binary: str,
    receptor: Path,
    ligand: Path,
    out: Path,
    center: tuple[float, float, float],
) -> list[str]:
    """Build the AutoDock Vina command line."""

    return [
        binary,
        "--receptor",
        str(receptor),
        "--ligand",
        str(ligand),
        "--center_x",
        f"{center[0]:.3f}",
        "--center_y",
        f"{center[1]:.3f}",
        "--center_z",
        f"{center[2]:.3f}",
        "--size_x",
        f"{float(params.get('size_x') or 20.0):.3f}",
        "--size_y",
        f"{float(params.get('size_y') or 20.0):.3f}",
        "--size_z",
        f"{float(params.get('size_z') or 20.0):.3f}",
        "--num_modes",
        str(int(params.get("num_modes") or 9)),
        "--exhaustiveness",
        str(int(params.get("exhaustiveness") or 8)),
        "--seed",
        str(int(params.get("seed") or 42)),
        "--out",
        str(out),
        "--log",
        str(out.with_suffix(".log")),
    ]


def stack_poses(poses: list[dict]) -> tuple[np.ndarray, dict, dict]:
    """Stack poses into ``[pose, atom, field]`` with x/y/z/charge/atomic_number."""

    fields = ("x", "y", "z", "charge", "atomic_number")
    field_labels = {name: index for index, name in enumerate(fields)}
    pose_labels: dict[str, int] = {}
    atom_labels: dict[str, int] = {}
    frames: list[np.ndarray] = []
    n_atoms = None
    for pose in poses:
        index = pose["index"]
        pose_labels[f"pose{index}"] = index - 1
        if n_atoms is None:
            n_atoms = len(pose["atoms"])
            for position in range(1, n_atoms + 1):
                atom_labels[f"atom{position}"] = position - 1
        elif len(pose["atoms"]) != n_atoms:
            raise StepError(
                f"vina_dock: pose {index} holds {len(pose['atoms'])} atoms, "
                f"expected {n_atoms}"
            )
        rows = []
        for position, atom in enumerate(pose["atoms"]):
            rows.append(
                [
                    atom["x"],
                    atom["y"],
                    atom["z"],
                    atom["charge"],
                    float(_ATOMIC_NUMBER.get(atom["element"], 0)),
                ]
            )
        frames.append(np.asarray(rows, dtype=np.float32))
    data = np.stack(frames, axis=0)
    labels = {"pose": pose_labels, "atom": atom_labels, "field": field_labels}
    return data, labels, {"fields": list(fields)}


class VinaDockStep(Step):
    """Dock one ligand into a receptor with AutoDock Vina."""

    provider = "operon-core"

    parameters_file = "vina_dock.VinaDockStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vina_dock",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AutoDock Vina docking",
        "description": (
            "Run AutoDock Vina with a PDBQT receptor and ligand, then return every "
            "docked pose as a [pose, atom, field] table together with the affinity "
            "table parsed from the Vina log."
        ),
        "category": "Machine Learning",
        "icon": "Flask",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 3, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        del inputs
        params = ctx.step_params
        out_name = str(params.get("output") or "pose")
        receptor = Path(str(params.get("receptor_path") or "")).expanduser()
        ligand = Path(str(params.get("ligand_path") or "")).expanduser()
        for label, path in (("receptor_path", receptor), ("ligand_path", ligand)):
            if not str(path) or str(path) == ".":
                raise StepError(f"vina_dock: {label} is required")
            if not path.is_file():
                raise StepError(f"vina_dock: {label} {path} is not a file")
            if path.suffix.lower() != ".pdbqt":
                raise StepError(
                    f"vina_dock: {label} {path.name} is not a .pdbqt file; convert it "
                    "with ADFR/AutoDockTools or Meeko first"
                )

        if bool(params.get("auto_center", True)):
            center = ligand_centroid(ligand)
        else:
            center = (
                float(params.get("center_x") or 0.0),
                float(params.get("center_y") or 0.0),
                float(params.get("center_z") or 0.0),
            )

        binary = str(params.get("vina_path") or "vina")
        timeout = int(params.get("timeout_seconds") or 1800)
        import shutil

        with tempfile.TemporaryDirectory(prefix="vina_") as work:
            out = Path(work) / "poses.pdbqt"
            command = docking_command(params, binary, receptor, ligand, out, center)
            if binary.lower().endswith(".py"):
                # A script runner cannot be executed directly on Windows.
                command = [sys.executable] + command
            try:
                completed = subprocess.run(
                    command, capture_output=True, text=True, timeout=timeout
                )
            except FileNotFoundError as exc:
                raise StepError(
                    f"vina_dock: '{binary}' was not found on PATH; install AutoDock Vina "
                    "and point vina_path at the executable"
                ) from exc
            except subprocess.TimeoutExpired as exc:
                raise StepError(f"vina_dock: Vina timed out after {timeout} s") from exc
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
                raise StepError(
                    f"vina_dock: Vina failed with exit code {completed.returncode}: {tail}"
                )
            if not out.is_file():
                raise StepError(f"vina_dock: Vina produced no pose file at {out}")
            directory = output_directory(ctx, "vina_dock")
            native_pose = directory / "poses.pdbqt"
            shutil.copyfile(out, native_pose)
            poses = parse_poses(out)
            log_path = out.with_suffix(".log")
            log = parse_vina_log(log_path.read_text(encoding="utf-8", errors="replace")) if log_path.is_file() else {"affinities": []}

        data, labels, extra = stack_poses(poses)
        affinities = log["affinities"][: len(poses)]
        form = Form(
            data,
            dims=["pose", "atom", "field"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_poses": len(poses),
                "fields": extra["fields"],
                "affinities": affinities,
                "best_affinity": affinities[0] if affinities else float("nan"),
                "rmsd_lb": log.get("rmsd_lb", [])[: len(poses)],
                "rmsd_ub": log.get("rmsd_ub", [])[: len(poses)],
                "receptor_path": str(receptor),
                "ligand_path": str(ligand),
                "vina_path": binary,
            },
        )
        result_files = [result_file("poses", native_pose, "pdbqt", "Vina docking poses")]
        remember_native(ctx, out_name, result_files)
        self._result_files = result_files
        ctx[out_name] = form
        self._export_data = form

    def export(self, ctx) -> dict:
        form = self._export_data
        return {
            "operator": "vina_dock",
            "result_files": getattr(self, "_result_files", []),
            "n_poses": int(form.info["n_poses"]),
            "best_affinity": float(form.info["best_affinity"]),
        }
