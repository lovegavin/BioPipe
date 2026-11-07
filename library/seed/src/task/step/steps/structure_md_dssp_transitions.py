"""structure_md_dssp_transitions: secondary-structure state kinetics."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_dssp_segments import parse_dssp, run_dssp
from src.task.step.steps.structure_md_ss_occupancy import atom_lines, load_frames, write_frame

_THREE = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS", "Q": "GLN", "E": "GLU",
    "G": "GLY", "H": "HIS", "I": "ILE", "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE",
    "P": "PRO", "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}

_HELIX = {"H", "G", "I"}
_STRAND = {"E", "B"}
CLASSES = ("helix", "strand", "coil")


def coarse_state(code: str) -> int:
    """Map a DSSP code onto helix (0), strand (1) or coil (2)."""

    if code in _HELIX:
        return 0
    if code in _STRAND:
        return 1
    return 2


def state_matrix(frames: np.ndarray, lines: list[str], labels: list[str], *, dssp: str, workdir: Path, timeout: int) -> np.ndarray:
    """Return the coarse DSSP state of every residue in every frame."""

    matrix = np.zeros((len(labels), len(frames)), dtype=int)
    for frame_index, coordinates in enumerate(frames):
        frame_path = workdir / f"frame_{frame_index:04d}.pdb"
        write_frame(lines, coordinates, frame_path)
        text = run_dssp(dssp, frame_path, workdir, timeout=timeout)
        records = parse_dssp(text)
        states = {
            f'{record["chain"]}:{_THREE.get(record["residue"], record["residue"])}:{record["number"]}': {
                "helix": 0,
                "strand": 1,
            }.get(record["state"], 2)
            for record in records
        }
        for residue_index, label in enumerate(labels):
            if label not in states:
                raise StepError(f"structure_md_dssp_transitions: residue {label} is missing from the DSSP output")
            matrix[residue_index, frame_index] = states[label]
    return matrix


def transition_totals(matrix: np.ndarray, lag: int = 1) -> np.ndarray:
    """Count state transitions between frames separated by a lag."""

    if lag < 1:
        raise StepError("structure_md_dssp_transitions: lag must be at least 1")
    counts = np.zeros((3, 3), dtype=int)
    for residue in range(matrix.shape[0]):
        for frame in range(matrix.shape[1] - lag):
            counts[matrix[residue, frame], matrix[residue, frame + lag]] += 1
    return counts


def transition_rows(matrix: np.ndarray, labels: list[str], *, lag: int, frame_time_ps: float) -> list[dict]:
    """Summarise populations, transitions and dwell times per residue."""

    rows = []
    for residue, label in enumerate(labels):
        states = matrix[residue]
        counts = np.bincount(states, minlength=3).astype(float)
        probabilities = counts / counts.sum()
        transitions = int(np.sum(states[lag:] != states[:-lag]))
        dominant = CLASSES[int(np.argmax(probabilities))]
        dwell = float(len(states) / max(transitions + 1, 1))
        rows.append(
            {
                "label": label,
                "p_helix": probabilities[0],
                "p_strand": probabilities[1],
                "p_coil": probabilities[2],
                "transitions": transitions,
                "dominant": dominant,
                "dwell_frames": dwell,
                "dwell_ps": dwell * frame_time_ps,
            }
        )
    rows.sort(key=lambda row: (-row["transitions"], row["label"]))
    return rows


class StructureMdDsspTransitionsStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_dssp_transitions.StructureMdDsspTransitionsStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_dssp_transitions",
        "version": "1.0.0",
        "kind": "operator",
        "title": "二级结构状态转换",
        "description": (
            "Run DSSP on every trajectory frame, map codes onto helix/strand/coil, and "
            "report per-residue populations, transition counts and dwell times plus the "
            "global coarse transition matrix."
        ),
        "category": "Structure",
        "icon": "Waves",
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
        frames = load_frames(str(params.get("trajectory_path", "")))
        topology = Path(str(params.get("topology_path", ""))).expanduser()
        if not topology.is_file():
            raise StepError(f"structure_md_dssp_transitions: topology_path {topology} is not a file")
        lines = atom_lines(topology)
        if len(lines) != frames.shape[1]:
            raise StepError(
                f"structure_md_dssp_transitions: the trajectory has {frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        labels = [f"{line[21].strip()}:{line[17:20].strip()}:{int(line[22:26])}" for line in lines]
        unique = []
        for label in labels:
            if label not in unique:
                unique.append(label)
        lag = int(params.get("lag_frames", 1))
        frame_time_ps = float(params.get("frame_time_ps", 0.2))
        if frame_time_ps <= 0:
            raise StepError("structure_md_dssp_transitions: frame_time_ps must be positive")
        dssp = str(params.get("dssp_path", "mkdssp"))
        with tempfile.TemporaryDirectory(prefix="dssp_transitions_") as temporary:
            matrix = state_matrix(
                frames,
                lines,
                unique,
                dssp=dssp,
                workdir=Path(temporary),
                timeout=int(params.get("timeout_seconds", 300)),
            )
        counts = transition_totals(matrix, lag)
        rows = transition_rows(matrix, unique, lag=lag, frame_time_ps=frame_time_ps)
        limit = int(params.get("n_residues", 0))
        if limit > 0:
            rows = rows[:limit]
        out = str(params.get("output", "transitions"))
        names = {row["label"]: index for index, row in enumerate(rows)}
        table = [[row["p_helix"], row["p_strand"], row["p_coil"], float(row["transitions"]), row["dwell_frames"]] for row in rows]
        ctx[out] = Form(
            data=np.asarray(table, dtype=np.float32),
            dims=["residue", "statistic"],
            labels={"residue": names, "statistic": {"p_helix": 0, "p_strand": 1, "p_coil": 2, "transitions": 3, "dwell_frames": 4}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_residues": len(unique),
                "n_reported": len(rows),
                "lag_frames": lag,
                "frame_time_ps": frame_time_ps,
                "transition_matrix": [[int(value) for value in row] for row in counts],
                "classes": list(CLASSES),
                "total_transitions": int(sum(row["transitions"] for row in rows)),
                "dssp_path": dssp,
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_residues": len(unique),
            "lag_frames": lag,
            "total_transitions": int(sum(row["transitions"] for row in rows)),
            "dominant_classes": {name: int(np.sum([1 for row in rows if row["dominant"] == name])) for name in CLASSES},
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
