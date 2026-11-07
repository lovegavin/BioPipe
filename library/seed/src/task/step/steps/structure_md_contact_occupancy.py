"""structure_md_contact_occupancy: residue contact frequencies along a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_contact_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_contact_occupancy: trajectory must have shape (frames, atoms, 3)")
    if frames.shape[0] == 0:
        raise StepError("structure_md_contact_occupancy: the trajectory holds no frame")
    return np.asarray(frames, dtype=float) * 10.0


def residue_groups(lines: list[str], chains: set[str] | None = None) -> tuple[dict[tuple, np.ndarray], list[tuple]]:
    groups: dict[tuple, list[int]] = {}
    order: list[tuple] = []
    for index, line in enumerate(lines):
        element = line[76:78].strip().upper()
        if element == "H" or line[12:16].strip().startswith("H"):
            continue
        key = (line[21].strip(), line[17:20].strip(), int(line[22:26]))
        if chains and key[0] not in chains:
            continue
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(index)
    if len(order) < 2:
        raise StepError("structure_md_contact_occupancy: at least two residues with heavy atoms are required")
    return {key: np.asarray(indices, dtype=int) for key, indices in groups.items()}, order


def frame_distances(coordinates: np.ndarray, indices_a: np.ndarray, indices_b: np.ndarray) -> float:
    tree = cKDTree(coordinates[indices_b])
    distances, _ = tree.query(coordinates[indices_a], k=1)
    return float(np.min(distances))


def contact_table(
    distances: np.ndarray,
    keys: list[tuple],
    cutoff: float,
    min_occupancy: float,
) -> list[dict]:
    """Aggregate pairwise minimum distances into contact occupancies."""

    rows = []
    frames = distances.shape[0]
    for index, key in enumerate(keys):
        values = distances[:, index]
        occupancy = float(np.mean(values <= cutoff))
        if occupancy < min_occupancy:
            continue
        rows.append(
            {
                "pair": key,
                "occupancy": occupancy,
                "mean_distance": float(np.mean(values)),
                "min_distance": float(np.min(values)),
            }
        )
    rows.sort(key=lambda item: (-item["occupancy"], item["mean_distance"]))
    return rows


class StructureMdContactOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_contact_occupancy.StructureMdContactOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_contact_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 残基接触占有率",
        "description": (
            "Compute per-residue-pair heavy-atom minimum distances across MD frames and "
            "report how often each pair stays in contact, with mean and minimum distances."
        ),
        "category": "Structure",
        "icon": "GridNine",
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
        frames = load_frames(Path(str(params.get("trajectory_path", ""))))
        topology = Path(str(params.get("topology_path", ""))).expanduser()
        if not topology.is_file():
            raise StepError(f"structure_md_contact_occupancy: topology_path {topology} is not a file")
        lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_contact_occupancy: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        chains = {token.strip() for token in str(params.get("chains", "")).split(",") if token.strip()}
        groups, order = residue_groups(lines, chains)
        stride = max(1, int(params.get("stride", 1)))
        selected = list(range(0, frames.shape[0], stride))
        if len(selected) < 2:
            raise StepError("structure_md_contact_occupancy: at least two frames are required")
        keys = []
        pair_distances = []
        for i, first in enumerate(order):
            for second in order[i + 1 :]:
                keys.append((first, second))
        distances = np.zeros((len(selected), len(keys)), dtype=float)
        for frame_index, frame in enumerate(selected):
            coordinates = frames[frame]
            for pair_index, (first, second) in enumerate(keys):
                distances[frame_index, pair_index] = frame_distances(coordinates, groups[first], groups[second])
        cutoff = float(params.get("cutoff", 5.0))
        min_occupancy = float(params.get("min_occupancy", 0.2))
        rows = contact_table(distances, keys, cutoff, min_occupancy)
        if not rows:
            raise StepError("structure_md_contact_occupancy: no residue pair reaches min_occupancy at the cutoff")
        values = np.asarray([[row["occupancy"], row["mean_distance"], row["min_distance"]] for row in rows], dtype=np.float32)
        out_dim = str(params.get("contact_dim", "contact"))
        out_name = str(params.get("output", "contacts"))
        labels = {f"{first[0]}:{first[2]}-{second[0]}:{second[2]}": index for index, (first, second) in enumerate((row["pair"] for row in rows))}
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={out_dim: labels, "statistic": {"occupancy": 0, "mean_distance": 1, "min_distance": 2}},
            info={
                "missing_code": np.nan,
                "n_frames": len(selected),
                "n_pairs": len(keys),
                "n_contacts": len(rows),
                "cutoff": cutoff,
                "min_occupancy": min_occupancy,
                "stride": stride,
            },
        )
        self._export_data = {"contacts": len(rows), "n_pairs": len(keys), "n_frames": len(selected)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
