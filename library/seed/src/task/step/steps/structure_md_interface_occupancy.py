"""structure_md_interface_occupancy: persistent interface residues over a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, residue_labels


def load_frames(path: str | Path) -> np.ndarray:
    """Load a (frames, atoms, 3) coordinate array."""

    frames = np.load(Path(path), allow_pickle=False)
    data = np.asarray(frames, dtype=np.float64)
    if data.ndim != 3 or data.shape[2] != 3:
        raise StepError(f"structure_md_interface_occupancy: expected [frames, atoms, 3] coordinates, got {data.shape}")
    if data.shape[0] < 2:
        raise StepError("structure_md_interface_occupancy: at least two frames are required")
    return data


def topology_table(path: str | Path):
    """Return residue labels, chains and a heavy-atom mask for the topology."""

    form = read_source(Path(path), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})
    labels = residue_labels(form, "field")
    chain = np.array([str(label).split(":")[0] for label in labels])
    elements = np.array([str(value).upper() for value in form.data[:, column_index(form, "field", "element")]])
    heavy = elements != "H"
    return labels, chain, heavy


def occupancy_rows(frames: np.ndarray, labels: np.ndarray, chain: np.ndarray, heavy: np.ndarray, *, binder_chains: set[str], target_chains: set[str], cutoff: float):
    """Count, per residue on either side, the frames with a cross-chain contact."""

    if frames.shape[1] != labels.shape[0]:
        raise StepError(f"structure_md_interface_occupancy: trajectory has {frames.shape[1]} atoms but topology has {labels.shape[0]}")
    binder = heavy & np.isin(chain, list(binder_chains))
    target = heavy & np.isin(chain, list(target_chains))
    if not binder.any() or not target.any():
        raise StepError("structure_md_interface_occupancy: both sides need heavy atoms in the selected chains")
    binder_labels = labels[binder]
    target_labels = labels[target]
    hits: dict[str, int] = {str(label): 0 for label in dict.fromkeys(binder_labels.tolist() + target_labels.tolist())}
    min_dist: dict[str, float] = {label: float("inf") for label in hits}
    for frame in frames:
        query = frame[binder]
        reference = frame[target]
        tree = cKDTree(reference)
        distances, indices = tree.query(query, k=1, distance_upper_bound=cutoff)
        near = np.isfinite(distances)
        for label in np.unique(binder_labels[near]):
            hits[str(label)] += 1
        for label in np.unique(target_labels[indices[near]]):
            hits[str(label)] += 1
        for label, index, distance in zip(binder_labels[near], indices[near], distances[near]):
            key = str(label)
            if distance < min_dist[key]:
                min_dist[key] = float(distance)
            partner = str(target_labels[int(index)])
            if distance < min_dist[partner]:
                min_dist[partner] = float(distance)
    rows = [
        {
            "label": label,
            "occupancy": hits[label] / frames.shape[0],
            "min_distance": min_dist[label] if np.isfinite(min_dist[label]) else float("nan"),
            "n_frames": hits[label],
        }
        for label in hits
    ]
    rows = [row for row in rows if row["n_frames"] > 0]
    rows.sort(key=lambda item: (-item["occupancy"], item["label"]))
    return rows


def select_chains(params: dict, chain: np.ndarray) -> tuple[set[str], set[str]]:
    """Resolve binder and target chains, defaulting to the first chain vs the rest."""

    present = sorted(set(str(value) for value in chain))
    binder_text = str(params.get("binder_chains", "") or "").strip()
    target_text = str(params.get("target_chains", "") or "").strip()
    binder = set(part.strip() for part in binder_text.split(",") if part.strip())
    target = set(part.strip() for part in target_text.split(",") if part.strip())
    if not binder and not target:
        binder = {present[0]}
        target = set(present[1:])
    elif not binder:
        binder = set(present) - target
    elif not target:
        target = set(present) - binder
    missing = (binder | target) - set(present)
    if missing:
        raise StepError(f"structure_md_interface_occupancy: chain(s) {sorted(missing)} are absent from the topology")
    return binder, target


class StructureMdInterfaceOccupancyStep(Step):
    provider = "biopipe-core"
    parameters_file = "structure_md_interface_occupancy.StructureMdInterfaceOccupancyStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "id": "structure_md_interface_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD interface occupancy",
        "description": "Report which interface residues stay in contact across a trajectory.",
        "category": "Structure",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        frames = load_frames(str(params.get("trajectory_path", "")))
        labels, chain, heavy = topology_table(str(params.get("topology_path", "")))
        binder, target = select_chains(params, chain)
        cutoff = float(params.get("cutoff", 5.0))
        if cutoff <= 0:
            raise StepError("structure_md_interface_occupancy: cutoff must be positive")
        rows = occupancy_rows(frames, labels, chain, heavy, binder_chains=binder, target_chains=target, cutoff=cutoff)
        if not rows or all(row["n_frames"] == 0 for row in rows):
            raise StepError("structure_md_interface_occupancy: no cross-chain contact was found at this cutoff")
        report_dim = str(params.get("residue_dim", "residue"))
        data = np.array([[row["occupancy"], row["min_distance"], float(row["n_frames"])] for row in rows], dtype=np.float32)
        out = params.get("output", "interface")
        persistent = sum(1 for row in rows if row["occupancy"] >= 0.9)
        ctx[out] = Form(
            data=data,
            dims=[report_dim, "statistic"],
            labels={
                report_dim: {row["label"]: index for index, row in enumerate(rows)},
                "statistic": {"occupancy": 0, "min_distance": 1, "n_frames": 2},
            },
            info={
                "missing_code": np.nan,
                "n_frames": int(frames.shape[0]),
                "cutoff": cutoff,
                "n_interface_residues": len(rows),
                "n_persistent": int(persistent),
                "binder_chains": sorted(binder),
                "target_chains": sorted(target),
            },
        )
        self._export_data = {
            "output": out,
            "n_interface_residues": len(rows),
            "n_persistent": int(persistent),
        }
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
