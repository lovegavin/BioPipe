"""structure_md_rotamer_states: chi1 rotamer populations, entropy and transitions."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_chi_angles import CHI1, dihedral
from src.task.step.steps.structure_md_pca import load_frames

ROTAMERS = ("g+", "t", "g-")
ROTAMER_ANGLES = (60.0, 180.0, -60.0)


def chi1_atoms(topology: Path) -> list[dict]:
    """Return chi1 atom indices and residue labels from a topology PDB."""

    path = Path(topology).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_rotamer_states: topology_path {path} is not a file")
    atoms: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for index, line in enumerate(path.read_text().splitlines()):
        if not line.startswith("ATOM"):
            continue
        name = line[12:16].strip()
        key = f"{line[21].strip()}:{line[17:20].strip()}:{line[22:26].strip()}"
        if key not in atoms:
            atoms[key] = {}
            order.append(key)
        atoms[key][name] = index
    records = []
    for key in order:
        chain, resname, number = key.split(":")
        if resname not in CHI1:
            continue
        four = ("N", "CA", "CB", CHI1[resname])
        if all(name in atoms[key] for name in four):
            records.append({"label": key, "indices": tuple(atoms[key][name] for name in four)})
    if not records:
        raise StepError("structure_md_rotamer_states: no residue carries a complete chi1 atom set")
    return records


def rotamer(angle: float) -> str:
    """Classify a chi1 angle into the nearest of the three staggered rotamers."""

    best = min(range(3), key=lambda index: abs(((angle - ROTAMER_ANGLES[index] + 180.0) % 360.0) - 180.0))
    return ROTAMERS[best]


def rotamer_trajectory(records: list[dict], frames: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return chi1 angles and rotamer codes of shape (residues, frames)."""

    angles = np.zeros((len(records), len(frames)))
    codes = np.zeros((len(records), len(frames)), dtype=int)
    for residue, record in enumerate(records):
        for frame_index, coordinates in enumerate(frames):
            value = dihedral(*(coordinates[index] for index in record["indices"]))
            angles[residue, frame_index] = value
            codes[residue, frame_index] = ROTAMERS.index(rotamer(value))
    return angles, codes


def rotamer_rows(records: list[dict], angles: np.ndarray, codes: np.ndarray) -> list[dict]:
    """Summarise populations, entropy and transitions per residue."""

    rows = []
    for residue, record in enumerate(records):
        counts = np.bincount(codes[residue], minlength=3).astype(float)
        probabilities = counts / counts.sum()
        nonzero = probabilities[probabilities > 0]
        entropy = float(-(nonzero * np.log(nonzero)).sum())
        transitions = int(np.sum(codes[residue, 1:] != codes[residue, :-1]))
        rows.append(
            {
                "label": record["label"],
                "p_gplus": float(probabilities[0]),
                "p_trans": float(probabilities[1]),
                "p_gminus": float(probabilities[2]),
                "entropy": entropy,
                "transitions": transitions,
                "mean_chi1": float(angles[residue].mean()),
            }
        )
    rows.sort(key=lambda row: (-row["entropy"], -row["transitions"], row["label"]))
    return rows


class StructureMdRotamerStatesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_rotamer_states.StructureMdRotamerStatesStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_rotamer_states",
        "version": "1.0.0",
        "kind": "operator",
        "title": "侧链旋转异构状态",
        "description": (
            "Classify chi1 side-chain rotamers over a trajectory and report "
            "populations, rotamer entropy and the number of state transitions."
        ),
        "category": "Structure",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_rotamer_states")
        records = chi1_atoms(Path(str(params.get("topology_path", ""))))
        if max(index for record in records for index in record["indices"]) >= frames.shape[1]:
            raise StepError("structure_md_rotamer_states: the topology indexes atoms beyond the trajectory")
        angles, codes = rotamer_trajectory(records, frames)
        rows = rotamer_rows(records, angles, codes)
        limit = int(params.get("n_residues", 0))
        if limit > 0:
            rows = rows[:limit]
        out = str(params.get("output", "rotamers"))
        names = {row["label"]: index for index, row in enumerate(rows)}
        table = [[row["p_gplus"], row["p_trans"], row["p_gminus"], row["entropy"], float(row["transitions"])] for row in rows]
        ctx[out] = Form(
            data=np.asarray(table, dtype=np.float32),
            dims=["residue", "statistic"],
            labels={"residue": names, "statistic": {"p_gplus": 0, "p_trans": 1, "p_gminus": 2, "entropy": 3, "transitions": 4}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_residues": len(rows),
                "mean_entropy": float(np.mean([row["entropy"] for row in rows])) if rows else 0.0,
                "max_entropy": float(max(row["entropy"] for row in rows)) if rows else 0.0,
                "total_transitions": int(sum(row["transitions"] for row in rows)),
                "n_topology_residues": len(records),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_residues": len(rows),
            "mean_entropy": float(np.mean([row["entropy"] for row in rows])) if rows else 0.0,
            "total_transitions": int(sum(row["transitions"] for row in rows)),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
