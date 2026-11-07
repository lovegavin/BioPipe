"""structure_md_sasa_occupancy: per-residue SASA statistics along a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_sasa_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_sasa_occupancy: trajectory must have shape (frames, atoms, 3)")
    if frames.shape[0] == 0:
        raise StepError("structure_md_sasa_occupancy: the trajectory holds no frame")
    return np.asarray(frames, dtype=float) * 10.0


def residue_sasa(
    topology_path: Path,
    frames: np.ndarray,
    *,
    probe_radius: float = 1.4,
    n_sphere_points: int = 92,
) -> tuple[np.ndarray, list[str]]:
    """Return per-frame, per-residue SASA in square angstroms."""

    from src.task.step.steps.interface_bsa import sasa_per_atom, vdw_radii

    topology = Path(topology_path).expanduser()
    if not topology.is_file():
        raise StepError(f"structure_md_sasa_occupancy: topology_path {topology} is not a file")
    lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
    if frames.shape[1] != len(lines):
        raise StepError(
            "structure_md_sasa_occupancy: the trajectory has "
            f"{frames.shape[1]} atoms but the topology has {len(lines)}"
        )
    elements = np.array([line[76:78].strip().upper() or line[12:16].strip()[0] for line in lines])
    radii = vdw_radii(elements)
    labels = []
    residue_index = []
    seen: dict[str, int] = {}
    for line in lines:
        label = f"{line[21].strip()}:{line[17:20].strip()}:{int(line[22:26])}"
        if label not in seen:
            seen[label] = len(labels)
            labels.append(label)
        residue_index.append(seen[label])
    residue_index = np.asarray(residue_index, dtype=int)
    values = np.zeros((frames.shape[0], len(labels)), dtype=float)
    for frame_index, coordinates in enumerate(frames):
        per_atom = sasa_per_atom(coordinates, radii, probe_radius=float(probe_radius), n_points=int(n_sphere_points))
        np.add.at(values[frame_index], residue_index, per_atom)
    return values, labels


def sasa_rows(values: np.ndarray, labels: list[str], *, exposed_threshold: float = 1.0) -> list[dict]:
    rows = []
    for index, label in enumerate(labels):
        series = values[:, index]
        rows.append(
            {
                "residue": label,
                "mean_sasa": float(np.mean(series)),
                "min_sasa": float(np.min(series)),
                "max_sasa": float(np.max(series)),
                "exposed_fraction": float(np.mean(series >= exposed_threshold)),
            }
        )
    rows.sort(key=lambda item: (item["mean_sasa"], item["residue"]))
    return rows


class StructureMdSasaOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_sasa_occupancy.StructureMdSasaOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_sasa_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 残留溶剂可及面积统计",
        "description": (
            "Compute per-residue solvent-accessible surface area for every MD frame with "
            "mdtraj Shrake-Rupley and report mean, minimum, maximum and exposed fraction."
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
        frames = load_frames(Path(str(params.get("trajectory_path", ""))))
        stride = max(1, int(params.get("stride", 1)))
        selected = frames[::stride]
        if selected.shape[0] < 1:
            raise StepError("structure_md_sasa_occupancy: at least one frame is required")
        values, labels = residue_sasa(
            Path(str(params.get("topology_path", ""))),
            selected,
            probe_radius=float(params.get("probe_radius", 1.4)),
            n_sphere_points=int(params.get("n_sphere_points", 960)),
        )
        rows = sasa_rows(values, labels, exposed_threshold=float(params.get("exposed_threshold", 1.0)))
        data = np.asarray(
            [[row["mean_sasa"], row["min_sasa"], row["max_sasa"], row["exposed_fraction"]] for row in rows],
            dtype=np.float32,
        )
        out_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "sasa"))
        ctx[out_name] = Form(
            data=data,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {row["residue"]: index for index, row in enumerate(rows)},
                "statistic": {"mean_sasa": 0, "min_sasa": 1, "max_sasa": 2, "exposed_fraction": 3},
            },
            info={
                "missing_code": np.nan,
                "n_frames": int(selected.shape[0]),
                "n_residues": len(rows),
                "probe_radius": float(params.get("probe_radius", 1.4)),
                "exposed_threshold": float(params.get("exposed_threshold", 1.0)),
                "mean_sasa": float(np.mean(data[:, 0])),
            },
        )
        self._export_data = {"n_frames": int(selected.shape[0]), "n_residues": len(rows), "mean_sasa": float(np.mean(data[:, 0]))}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
