"""structure_md_ligand_rmsd: ligand displacement after receptor superposition."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_ligand_rmsd: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_ligand_rmsd: trajectory must have shape (frames, atoms, 3)")
    return np.asarray(frames, dtype=float) * 10.0


def superposition(mobile: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, float]:
    mobile_center = mobile.mean(axis=0)
    reference_center = reference.mean(axis=0)
    covariance = (mobile - mobile_center).T @ (reference - reference_center)
    left, _, right = np.linalg.svd(covariance)
    determinant = np.linalg.det(left @ right)
    correction = np.diag([1.0, 1.0, 1.0 if determinant >= 0 else -1.0])
    rotation = left @ correction @ right
    translation = reference_center - mobile_center @ rotation
    aligned = mobile @ rotation + translation
    rmsd = float(np.sqrt(np.mean(np.sum((aligned - reference) ** 2, axis=1))))
    return rotation, translation, rmsd


def select_indices(lines: list[str], chains: set[str], ligand_resname: str) -> tuple[np.ndarray, np.ndarray]:
    receptor = []
    ligand = []
    for index, line in enumerate(lines):
        chain = line[21].strip()
        resname = line[17:20].strip().upper()
        atom = line[12:16].strip().upper()
        if resname == ligand_resname.upper():
            ligand.append(index)
        elif (not chains or chain in chains) and atom == "CA":
            receptor.append(index)
    if len(receptor) < 3:
        raise StepError("structure_md_ligand_rmsd: at least three receptor CA atoms are required")
    if not ligand:
        raise StepError(f"structure_md_ligand_rmsd: no '{ligand_resname}' atoms were found")
    return np.asarray(receptor, dtype=int), np.asarray(ligand, dtype=int)


def ligand_rmsd_series(frames: np.ndarray, receptor: np.ndarray, ligand: np.ndarray) -> np.ndarray:
    reference = frames[0]
    values = np.zeros(frames.shape[0], dtype=float)
    for index, frame in enumerate(frames):
        rotation, translation, _ = superposition(frame[receptor], reference[receptor])
        moved = frame[ligand] @ rotation + translation
        reference_ligand = reference[ligand]
        values[index] = float(np.sqrt(np.mean(np.sum((moved - reference_ligand) ** 2, axis=1))))
    return values


class StructureMdLigandRmsdStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_ligand_rmsd.StructureMdLigandRmsdStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_ligand_rmsd",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 配体位移 RMSD",
        "description": (
            "Superpose each MD frame on the first frame using receptor CA atoms and report "
            "the ligand RMSD after superposition, summarising mean, maximum and final values."
        ),
        "category": "Structure",
        "icon": "Flask",
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
            raise StepError(f"structure_md_ligand_rmsd: topology_path {topology} is not a file")
        lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_ligand_rmsd: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        chains = {token.strip() for token in str(params.get("receptor_chains", "")).split(",") if token.strip()}
        receptor, ligand = select_indices(lines, chains, str(params.get("ligand_resname", "LIG")))
        stride = max(1, int(params.get("stride", 1)))
        selected = frames[::stride]
        if selected.shape[0] < 2:
            raise StepError("structure_md_ligand_rmsd: at least two frames are required")
        values = ligand_rmsd_series(selected, receptor, ligand)
        data = np.asarray([[value] for value in values], dtype=np.float32)
        out_dim = str(params.get("frame_dim", "frame"))
        out_name = str(params.get("output", "ligand_rmsd"))
        ctx[out_name] = Form(
            data=data,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {f"frame{index + 1}": index for index in range(len(values))},
                "statistic": {"ligand_rmsd": 0},
            },
            info={
                "missing_code": np.nan,
                "n_frames": len(values),
                "n_receptor_atoms": int(receptor.size),
                "n_ligand_atoms": int(ligand.size),
                "mean_rmsd": float(np.mean(values)),
                "max_rmsd": float(np.max(values)),
                "final_rmsd": float(values[-1]),
                "stride": stride,
                "ligand_resname": str(params.get("ligand_resname", "LIG")),
            },
        )
        self._export_data = {"mean_rmsd": float(np.mean(values)), "max_rmsd": float(np.max(values)), "n_frames": len(values)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
