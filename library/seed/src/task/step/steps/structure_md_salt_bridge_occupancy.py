"""structure_md_salt_bridge_occupancy: salt-bridge persistence along a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

_ACID = {"ASP": ("OD1", "OD2"), "GLU": ("OE1", "OE2")}
_BASE = {"LYS": ("NZ",), "ARG": ("NH1", "NH2", "NE"), "HIS": ("ND1", "NE2")}


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_salt_bridge_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_salt_bridge_occupancy: trajectory must have shape (frames, atoms, 3)")
    return np.asarray(frames, dtype=float) * 10.0


def charge_groups(lines: list[str], chains: set[str] | None = None) -> tuple[list[tuple], list[tuple], dict]:
    """Collect acidic oxygen atoms and basic nitrogen atoms per residue."""

    acid: dict[tuple, list[int]] = {}
    base: dict[tuple, list[int]] = {}
    for index, line in enumerate(lines):
        chain = line[21].strip()
        if chains and chain not in chains:
            continue
        resname = line[17:20].strip().upper()
        number = int(line[22:26])
        atom = line[12:16].strip().upper()
        key = (chain, resname, number)
        if resname in _ACID and atom in _ACID[resname]:
            acid.setdefault(key, []).append(index)
        elif resname in _BASE and atom in _BASE[resname]:
            base.setdefault(key, []).append(index)
    if not acid or not base:
        raise StepError("structure_md_salt_bridge_occupancy: the topology carries no acidic/basic side-chain atoms")
    acids = sorted(acid)
    bases = sorted(base)
    atom_sets = {key: np.asarray(acid[key], dtype=int) for key in acids}
    atom_sets.update({key: np.asarray(base[key], dtype=int) for key in bases})
    return acids, bases, atom_sets


def pair_distances(coordinates: np.ndarray, acids: list[tuple], bases: list[tuple], atom_sets: dict) -> np.ndarray:
    values = np.zeros((len(acids), len(bases)), dtype=float)
    for i, acid in enumerate(acids):
        for j, base in enumerate(bases):
            tree = cKDTree(coordinates[atom_sets[base]])
            distances, _ = tree.query(coordinates[atom_sets[acid]], k=1)
            values[i, j] = float(np.min(distances))
    return values


def salt_bridge_rows(distances: np.ndarray, acids: list[tuple], bases: list[tuple], cutoff: float, min_occupancy: float) -> list[dict]:
    rows = []
    for i, acid in enumerate(acids):
        for j, base in enumerate(bases):
            values = distances[:, i, j]
            occupancy = float(np.mean(values <= cutoff))
            if occupancy < min_occupancy:
                continue
            rows.append(
                {
                    "acid": acid,
                    "base": base,
                    "occupancy": occupancy,
                    "mean_distance": float(np.mean(values)),
                    "min_distance": float(np.min(values)),
                }
            )
    rows.sort(key=lambda item: (-item["occupancy"], item["mean_distance"]))
    return rows


class StructureMdSaltBridgeOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_salt_bridge_occupancy.StructureMdSaltBridgeOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_salt_bridge_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 盐桥占有率",
        "description": (
            "Track acidic (ASP/GLU) and basic (LYS/ARG/HIS) side-chain atom pairs across MD "
            "frames and report the fraction of frames in which each pair stays within the "
            "salt-bridge cutoff, with mean and minimum distances."
        ),
        "category": "Structure",
        "icon": "ShareNetwork",
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
            raise StepError(f"structure_md_salt_bridge_occupancy: topology_path {topology} is not a file")
        lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_salt_bridge_occupancy: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        chains = {token.strip() for token in str(params.get("chains", "")).split(",") if token.strip()}
        acids, bases, atom_sets = charge_groups(lines, chains)
        stride = max(1, int(params.get("stride", 1)))
        selected = list(range(0, frames.shape[0], stride))
        if len(selected) < 2:
            raise StepError("structure_md_salt_bridge_occupancy: at least two frames are required")
        distances = np.zeros((len(selected), len(acids), len(bases)), dtype=float)
        for frame_index, index in enumerate(selected):
            distances[frame_index] = pair_distances(frames[index], acids, bases, atom_sets)
        cutoff = float(params.get("cutoff", 4.0))
        min_occupancy = float(params.get("min_occupancy", 0.2))
        rows = salt_bridge_rows(distances, acids, bases, cutoff, min_occupancy)
        if not rows:
            raise StepError("structure_md_salt_bridge_occupancy: no salt bridge reaches min_occupancy at the cutoff")
        values = np.asarray([[row["occupancy"], row["mean_distance"], row["min_distance"]] for row in rows], dtype=np.float32)
        out_dim = str(params.get("bond_dim", "salt_bridge"))
        out_name = str(params.get("output", "salt_bridges"))
        labels = {
            f"{row['acid'][0]}:{row['acid'][2]}:{row['acid'][1]}-{row['base'][0]}:{row['base'][2]}:{row['base'][1]}": index
            for index, row in enumerate(rows)
        }
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={out_dim: labels, "statistic": {"occupancy": 0, "mean_distance": 1, "min_distance": 2}},
            info={
                "missing_code": np.nan,
                "n_frames": len(selected),
                "n_acidic": len(acids),
                "n_basic": len(bases),
                "n_salt_bridges": len(rows),
                "cutoff": cutoff,
                "min_occupancy": min_occupancy,
                "stride": stride,
            },
        )
        self._export_data = {"salt_bridges": len(rows), "n_acidic": len(acids), "n_basic": len(bases)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
