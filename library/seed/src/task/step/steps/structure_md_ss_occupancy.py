"""structure_md_ss_occupancy: secondary-structure occupancy along a trajectory."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_dssp_segments import parse_dssp, run_dssp

HELIX = {"H", "G", "I"}
STRAND = {"E", "B"}


def load_frames(path: Path) -> np.ndarray:
    """Load an MD frame array (frames, atoms, 3) in nanometres."""

    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_ss_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_ss_occupancy: trajectory must have shape (frames, atoms, 3)")
    if frames.shape[0] == 0:
        raise StepError("structure_md_ss_occupancy: the trajectory holds no frame")
    return np.asarray(frames, dtype=float) * 10.0


def atom_lines(topology: Path) -> list[str]:
    path = Path(topology).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_ss_occupancy: topology_path {path} is not a file")
    return [line for line in path.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]


def write_frame(lines: list[str], coordinates: np.ndarray, path: Path) -> None:
    """Write one PDB frame by replacing the coordinates of the topology lines."""

    if coordinates.shape[0] != len(lines):
        raise StepError(
            "structure_md_ss_occupancy: the trajectory has "
            f"{coordinates.shape[0]} atoms but the topology has {len(lines)}"
        )
    output = ["HEADER    OPERON MD FRAME"]
    for line, (x, y, z) in zip(lines, coordinates):
        output.append(f"{line[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}")
    output.append("END")
    path.write_text("\n".join(output) + "\n")


def residue_key(line: str) -> str:
    return f"{line[21]}:{line[17:20].strip()}:{int(line[22:26])}"


def occupancy_rows(state_sets: list[dict[str, str]], labels: list[str]) -> list[dict]:
    """Aggregate per-frame DSSP states into per-residue occupancies."""

    rows = []
    for label in labels:
        states = [states.get(label, "coil") for states in state_sets]
        helix = sum(1 for state in states if state in HELIX) / len(states)
        strand = sum(1 for state in states if state in STRAND) / len(states)
        coil = max(0.0, 1.0 - helix - strand)
        if helix >= strand and helix >= coil:
            dominant = 2.0
        elif strand >= helix and strand >= coil:
            dominant = 1.0
        else:
            dominant = 0.0
        rows.append({"residue": label, "helix": helix, "strand": strand, "coil": coil, "dominant": dominant})
    return rows


class StructureMdSsOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_ss_occupancy.StructureMdSsOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_ss_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 轨迹二级结构占有率",
        "description": (
            "Run DSSP on sampled MD frames and report per-residue helix, strand and coil "
            "occupancies together with the dominant secondary-structure state."
        ),
        "category": "Structure",
        "icon": "ChartLine",
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
        trajectory = Path(str(params.get("trajectory_path", ""))).expanduser()
        topology = Path(str(params.get("topology_path", ""))).expanduser()
        frames = load_frames(trajectory)
        lines = atom_lines(topology)
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_ss_occupancy: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        stride = max(1, int(params.get("stride", 1)))
        selected = list(range(0, frames.shape[0], stride))
        if len(selected) < 2:
            raise StepError("structure_md_ss_occupancy: at least two frames are required for occupancy")
        labels = [residue_key(line) for line in lines]
        seen = set()
        ordered = []
        for label in labels:
            if label not in seen:
                seen.add(label)
                ordered.append(label)
        workdir = Path(tempfile.mkdtemp(prefix="md_ss_"))
        states = []
        for index in selected:
            frame_path = workdir / f"frame{index}.pdb"
            write_frame(lines, frames[index], frame_path)
            text = run_dssp(str(params.get("dssp_path", "mkdssp")), frame_path, workdir, timeout=int(params.get("timeout_seconds", 300)))
            records = parse_dssp(text)
            states.append({f"{record['chain']}:{record['residue']}:{record['number']}": record["state"] for record in records})
        rows = occupancy_rows(states, ordered)
        values = np.asarray([[row["helix"], row["strand"], row["coil"], row["dominant"]] for row in rows], dtype=np.float32)
        out_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "occupancy"))
        helix_mean = float(np.mean([row["helix"] for row in rows]))
        strand_mean = float(np.mean([row["strand"] for row in rows]))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {label: index for index, label in enumerate(rows_label["residue"] for rows_label in rows)},
                "statistic": {"helix": 0, "strand": 1, "coil": 2, "dominant": 3},
            },
            info={
                "missing_code": np.nan,
                "n_frames": len(selected),
                "n_residues": len(rows),
                "mean_helix": helix_mean,
                "mean_strand": strand_mean,
                "stride": stride,
            },
        )
        self._export_data = {"rows": rows, "n_frames": len(selected), "mean_helix": helix_mean, "mean_strand": strand_mean}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
