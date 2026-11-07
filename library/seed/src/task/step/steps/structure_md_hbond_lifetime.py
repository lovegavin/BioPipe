"""structure_md_hbond_lifetime: hydrogen-bond residence times along a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_hbond_occupancy import (
    candidate_bonds,
    donor_hydrogens,
    hbond_geometry,
    load_frames,
    parse_atoms,
)


def presence_matrix(
    atoms: list[dict],
    triples: list[tuple[int, int, int]],
    frames: np.ndarray,
    *,
    max_distance: float = 3.5,
    min_angle: float = 120.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return presence flags, distances and angles for every candidate triple."""

    count = len(frames)
    presence = np.zeros((len(triples), count), dtype=bool)
    distances = np.zeros((len(triples), count))
    angles = np.zeros((len(triples), count))
    for frame_index, coordinates in enumerate(frames):
        for index, (donor, hydrogen, acceptor) in enumerate(triples):
            distance, angle = hbond_geometry(coordinates, donor, hydrogen, acceptor)
            distances[index, frame_index] = distance
            angles[index, frame_index] = angle
            presence[index, frame_index] = distance <= max_distance and angle >= min_angle
    return presence, distances, angles


def run_lengths(flags: np.ndarray) -> list[int]:
    """Return the lengths of consecutive True runs."""

    runs: list[int] = []
    current = 0
    for flag in flags:
        if flag:
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return runs


def lifetime_rows(
    atoms: list[dict],
    triples: list[tuple[int, int, int]],
    presence: np.ndarray,
    distances: np.ndarray,
    *,
    frame_time_ps: float,
    min_occupancy: float,
) -> list[dict]:
    """Summarise per-pair residence statistics above an occupancy floor."""

    rows = []
    for index, (donor, hydrogen, acceptor) in enumerate(triples):
        flags = presence[index]
        occupancy = float(flags.mean())
        if occupancy < min_occupancy:
            continue
        runs = run_lengths(flags)
        transitions = int(sum(1 for left, right in zip(flags[:-1], flags[1:]) if right and not left))
        donor_atom = atoms[donor]
        acceptor_atom = atoms[acceptor]
        rows.append(
            {
                "donor": (donor_atom["chain"], donor_atom["resname"], donor_atom["number"], donor_atom["name"]),
                "acceptor": (acceptor_atom["chain"], acceptor_atom["resname"], acceptor_atom["number"], acceptor_atom["name"]),
                "occupancy": occupancy,
                "mean_lifetime_frames": float(np.mean(runs)) if runs else 0.0,
                "max_run_frames": int(max(runs)) if runs else 0,
                "n_runs": len(runs),
                "transitions": transitions,
                "mean_lifetime_ps": float(np.mean(runs) * frame_time_ps) if runs else 0.0,
                "mean_distance": float(np.mean(distances[index])),
            }
        )
    rows.sort(key=lambda item: (-item["mean_lifetime_frames"], -item["occupancy"]))
    return rows


class StructureMdHbondLifetimeStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_hbond_lifetime.StructureMdHbondLifetimeStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_hbond_lifetime",
        "version": "1.0.0",
        "kind": "operator",
        "title": "氢键寿命",
        "description": (
            "Detect hydrogen bonds per frame and report residence statistics: "
            "occupancy, mean and maximum continuous lifetime, transitions and picosecond conversion."
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
        frames = load_frames(str(params.get("trajectory_path", "")))
        topology = Path(str(params.get("topology_path", ""))).expanduser()
        if not topology.is_file():
            raise StepError(f"structure_md_hbond_lifetime: topology_path {topology} is not a file")
        atoms = parse_atoms([line for line in topology.read_text().splitlines() if line.startswith("ATOM")])
        if len(atoms) != frames.shape[1]:
            raise StepError(
                f"structure_md_hbond_lifetime: the trajectory has {frames.shape[1]} atoms but the topology has {len(atoms)}"
            )
        donors = donor_hydrogens(atoms, frames[0])
        if not donors:
            raise StepError("structure_md_hbond_lifetime: the topology carries no hydrogen donor")
        triples = candidate_bonds(atoms, donors)
        presence, distances, _ = presence_matrix(
            atoms,
            triples,
            frames,
            max_distance=float(params.get("max_distance", 3.5)),
            min_angle=float(params.get("min_angle", 120.0)),
        )
        frame_time_ps = float(params.get("frame_time_ps", 0.2))
        if frame_time_ps <= 0:
            raise StepError("structure_md_hbond_lifetime: frame_time_ps must be positive")
        rows = lifetime_rows(
            atoms,
            triples,
            presence,
            distances,
            frame_time_ps=frame_time_ps,
            min_occupancy=float(params.get("min_occupancy", 0.5)),
        )
        if not rows:
            raise StepError("structure_md_hbond_lifetime: no hydrogen bond reaches min_occupancy")
        top = int(params.get("n_pairs", 20))
        rows = rows[:top]
        out = str(params.get("output", "lifetimes"))
        table = []
        labels = {}
        for index, row in enumerate(rows):
            table.append(
                [
                    row["occupancy"],
                    row["mean_lifetime_frames"],
                    float(row["max_run_frames"]),
                    float(row["transitions"]),
                    row["mean_distance"],
                ]
            )
            donor = ":".join(str(part) for part in row["donor"][:3]) + ":" + row["donor"][3]
            acceptor = ":".join(str(part) for part in row["acceptor"][:3]) + ":" + row["acceptor"][3]
            labels[f"{donor}-{acceptor}"] = index
        ctx[out] = Form(
            data=np.asarray(table, dtype=np.float32),
            dims=["hbond", "statistic"],
            labels={"hbond": labels, "statistic": {"occupancy": 0, "mean_lifetime_frames": 1, "max_run_frames": 2, "transitions": 3, "mean_distance": 4}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_candidates": len(triples),
                "n_reported": len(rows),
                "frame_time_ps": frame_time_ps,
                "max_lifetime_ps": float(rows[0]["mean_lifetime_ps"]),
                "max_occupancy": float(max(row["occupancy"] for row in rows)),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_candidates": len(triples),
            "n_reported": len(rows),
            "frame_time_ps": frame_time_ps,
            "max_lifetime_ps": float(rows[0]["mean_lifetime_ps"]),
            "max_occupancy": float(max(row["occupancy"] for row in rows)),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
