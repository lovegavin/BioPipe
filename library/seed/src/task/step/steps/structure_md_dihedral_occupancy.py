"""structure_md_dihedral_occupancy: phi/psi and Ramachandran occupancy over MD."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_phi_psi import REGIONS, dihedral, ramachandran_region


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_dihedral_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_dihedral_occupancy: trajectory must have shape (frames, atoms, 3)")
    return np.asarray(frames, dtype=float) * 10.0


def backbone_atoms(lines: list[str], chains: set[str] | None = None) -> list[dict]:
    """Collect N, CA and C indices per residue, in topology order."""

    residues: dict[tuple, dict] = {}
    order: list[tuple] = []
    for index, line in enumerate(lines):
        chain = line[21].strip()
        if chains and chain not in chains:
            continue
        key = (chain, int(line[22:26]), line[17:20].strip())
        name = line[12:16].strip().upper()
        if name not in ("N", "CA", "C"):
            continue
        if key not in residues:
            residues[key] = {"key": key}
            order.append(key)
        residues[key][name] = index
    complete = [residues[key] for key in order if all(atom in residues[key] for atom in ("N", "CA", "C"))]
    if len(complete) < 3:
        raise StepError("structure_md_dihedral_occupancy: at least three complete backbone residues are required")
    return complete


def frame_angles(coordinates: np.ndarray, residues: list[dict]) -> tuple[list[float], list[float]]:
    phi_values = []
    psi_values = []
    for position, residue in enumerate(residues):
        if position > 0:
            previous = residues[position - 1]
            phi = dihedral(
                coordinates[previous["C"]],
                coordinates[residue["N"]],
                coordinates[residue["CA"]],
                coordinates[residue["C"]],
            )
        else:
            phi = float("nan")
        if position + 1 < len(residues):
            following = residues[position + 1]
            psi = dihedral(
                coordinates[residue["N"]],
                coordinates[residue["CA"]],
                coordinates[residue["C"]],
                coordinates[following["N"]],
            )
        else:
            psi = float("nan")
        phi_values.append(phi)
        psi_values.append(psi)
    return phi_values, psi_values


def occupancy_table(
    phi: np.ndarray,
    psi: np.ndarray,
    labels: list[str],
) -> list[dict]:
    rows = []
    for index, label in enumerate(labels):
        regions = [ramachandran_region(phi[frame, index], psi[frame, index]) for frame in range(phi.shape[0])]
        counts = {name: regions.count(name) / len(regions) for name in REGIONS}
        dominant = max(REGIONS, key=lambda name: (counts[name], -REGIONS.index(name)))
        rows.append(
            {
                "residue": label,
                "phi_mean": float(np.nanmean(phi[:, index])) if np.any(np.isfinite(phi[:, index])) else float("nan"),
                "psi_mean": float(np.nanmean(psi[:, index])) if np.any(np.isfinite(psi[:, index])) else float("nan"),
                "alpha_occupancy": counts["alpha"],
                "beta_occupancy": counts["beta"],
                "dominant": REGIONS.index(dominant),
            }
        )
    rows.sort(key=lambda item: (item["dominant"], item["residue"]))
    return rows


class StructureMdDihedralOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_dihedral_occupancy.StructureMdDihedralOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_dihedral_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 主链二面角占有率",
        "description": (
            "Compute backbone phi/psi for every MD frame, classify each frame into coarse "
            "Ramachandran regions and report per-residue region occupancies and means."
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
        frames = load_frames(Path(str(params.get("trajectory_path", ""))))
        topology = Path(str(params.get("topology_path", ""))).expanduser()
        if not topology.is_file():
            raise StepError(f"structure_md_dihedral_occupancy: topology_path {topology} is not a file")
        lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_dihedral_occupancy: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        chains = {token.strip() for token in str(params.get("chains", "")).split(",") if token.strip()}
        residues = backbone_atoms(lines, chains)
        stride = max(1, int(params.get("stride", 1)))
        selected = list(range(0, frames.shape[0], stride))
        if len(selected) < 2:
            raise StepError("structure_md_dihedral_occupancy: at least two frames are required")
        phi = np.full((len(selected), len(residues)), np.nan)
        psi = np.full((len(selected), len(residues)), np.nan)
        for frame_index, index in enumerate(selected):
            phi_values, psi_values = frame_angles(frames[index], residues)
            phi[frame_index] = phi_values
            psi[frame_index] = psi_values
        labels = [f"{residue['key'][0]}:{residue['key'][2]}:{residue['key'][1]}" for residue in residues]
        rows = occupancy_table(phi, psi, labels)
        values = np.asarray(
            [[row["phi_mean"], row["psi_mean"], row["alpha_occupancy"], row["beta_occupancy"], row["dominant"]] for row in rows],
            dtype=np.float32,
        )
        out_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "dihedrals"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {row["residue"]: index for index, row in enumerate(rows)},
                "statistic": {"phi_mean": 0, "psi_mean": 1, "alpha_occupancy": 2, "beta_occupancy": 3, "dominant": 4},
            },
            info={
                "missing_code": np.nan,
                "n_frames": len(selected),
                "n_residues": len(rows),
                "regions": list(REGIONS),
                "stride": stride,
            },
        )
        self._export_data = {"n_frames": len(selected), "n_residues": len(rows)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
