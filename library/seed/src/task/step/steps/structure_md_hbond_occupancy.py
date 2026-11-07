"""structure_md_hbond_occupancy: hydrogen-bond persistence along a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

_DONOR_ELEMENTS = {"N", "O", "S"}
_ACCEPTOR_ELEMENTS = {"N", "O", "S"}


def load_frames(path: Path) -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"structure_md_hbond_occupancy: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError("structure_md_hbond_occupancy: trajectory must have shape (frames, atoms, 3)")
    return np.asarray(frames, dtype=float) * 10.0


def parse_atoms(lines: list[str]) -> list[dict]:
    atoms = []
    for line in lines:
        atoms.append(
            {
                "element": line[76:78].strip().upper(),
                "name": line[12:16].strip().upper(),
                "resname": line[17:20].strip().upper(),
                "chain": line[21].strip(),
                "number": int(line[22:26]),
            }
        )
    return atoms


def donor_hydrogens(atoms: list[dict], coordinates: np.ndarray) -> list[tuple[int, int]]:
    """Pair every hydrogen with its nearest preceding heavy donor atom."""

    pairs = []
    for index, atom in enumerate(atoms):
        if atom["element"] != "H":
            continue
        best = None
        best_distance = 1.35
        for other, candidate in enumerate(atoms):
            if other == index or candidate["element"] not in _DONOR_ELEMENTS:
                continue
            distance = float(np.linalg.norm(coordinates[index] - coordinates[other]))
            if distance < best_distance:
                best = other
                best_distance = distance
        if best is not None:
            pairs.append((best, index))
    return pairs


def candidate_bonds(atoms: list[dict], donors: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    triples = []
    for donor, hydrogen in donors:
        for acceptor, atom in enumerate(atoms):
            if acceptor in (donor, hydrogen):
                continue
            if atom["element"] not in _ACCEPTOR_ELEMENTS:
                continue
            if atom["name"] in ("N", "CA", "C", "O") and atoms[donor]["name"] in ("N", "CA", "C", "O"):
                # backbone amide-to-carbonyl contacts are real; keep them
                pass
            triples.append((donor, hydrogen, acceptor))
    return triples


def hbond_geometry(coordinates: np.ndarray, donor: int, hydrogen: int, acceptor: int) -> tuple[float, float]:
    donor_pos = coordinates[donor]
    hydrogen_pos = coordinates[hydrogen]
    acceptor_pos = coordinates[acceptor]
    distance = float(np.linalg.norm(hydrogen_pos - acceptor_pos))
    first = donor_pos - hydrogen_pos
    second = acceptor_pos - hydrogen_pos
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator == 0.0:
        return distance, 0.0
    cosine = float(np.clip(np.dot(first, second) / denominator, -1.0, 1.0))
    return distance, float(np.degrees(np.arccos(cosine)))


def occupancy_rows(
    atoms: list[dict],
    triples: list[tuple[int, int, int]],
    distances: np.ndarray,
    angles: np.ndarray,
    *,
    occupancy: np.ndarray,
    cutoff: float,
    min_occupancy: float,
) -> list[dict]:
    rows = []
    for index, (donor, hydrogen, acceptor) in enumerate(triples):
        if occupancy[index] < min_occupancy:
            continue
        donor_atom = atoms[donor]
        acceptor_atom = atoms[acceptor]
        rows.append(
            {
                "donor": (donor_atom["chain"], donor_atom["resname"], donor_atom["number"], donor_atom["name"]),
                "acceptor": (acceptor_atom["chain"], acceptor_atom["resname"], acceptor_atom["number"], acceptor_atom["name"]),
                "occupancy": float(occupancy[index]),
                "mean_distance": float(np.mean(distances[index])),
                "mean_angle": float(np.mean(angles[index])),
            }
        )
    rows.sort(key=lambda item: (-item["occupancy"], item["mean_distance"]))
    return rows


class StructureMdHbondOccupancyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_hbond_occupancy.StructureMdHbondOccupancyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_hbond_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MD 氢键占有率",
        "description": (
            "Detect donor-H...acceptor hydrogen bonds from topology and per-frame geometry, "
            "and report the fraction of MD frames in which each residue pair stays bonded."
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
            raise StepError(f"structure_md_hbond_occupancy: topology_path {topology} is not a file")
        lines = [line for line in topology.read_text(errors="replace").splitlines() if line.startswith(("ATOM", "HETATM"))]
        if frames.shape[1] != len(lines):
            raise StepError(
                "structure_md_hbond_occupancy: the trajectory has "
                f"{frames.shape[1]} atoms but the topology has {len(lines)}"
            )
        atoms = parse_atoms(lines)
        chains = {token.strip() for token in str(params.get("chains", "")).split(",") if token.strip()}
        if chains:
            keep = [index for index, atom in enumerate(atoms) if atom["chain"] in chains]
            atoms = [atoms[index] for index in keep]
            frames = frames[:, keep]
            lines = [lines[index] for index in keep]
        donors = donor_hydrogens(atoms, frames[0])
        if not donors:
            raise StepError("structure_md_hbond_occupancy: the topology carries no hydrogen atoms")
        triples = candidate_bonds(atoms, donors)
        if not triples:
            raise StepError("structure_md_hbond_occupancy: no donor-H...acceptor triples were found")
        stride = max(1, int(params.get("stride", 1)))
        selected = list(range(0, frames.shape[0], stride))
        if len(selected) < 2:
            raise StepError("structure_md_hbond_occupancy: at least two frames are required")
        cutoff = float(params.get("cutoff", 3.5))
        angle_cutoff = float(params.get("angle_cutoff", 120.0))
        distances = np.zeros((len(triples), len(selected)), dtype=float)
        angles = np.zeros((len(triples), len(selected)), dtype=float)
        for frame_index, index in enumerate(selected):
            for bond_index, (donor, hydrogen, acceptor) in enumerate(triples):
                distances[bond_index, frame_index], angles[bond_index, frame_index] = hbond_geometry(
                    frames[index], donor, hydrogen, acceptor
                )
        bonded = (distances <= cutoff) & (angles >= angle_cutoff)
        occupancy = bonded.mean(axis=1)
        rows = occupancy_rows(
            atoms,
            triples,
            distances,
            angles,
            occupancy=occupancy,
            cutoff=cutoff,
            min_occupancy=float(params.get("min_occupancy", 0.2)),
        )
        if not rows:
            raise StepError("structure_md_hbond_occupancy: no hydrogen bond reaches min_occupancy")
        values = np.asarray([[row["occupancy"], row["mean_distance"], row["mean_angle"]] for row in rows], dtype=np.float32)
        out_dim = str(params.get("bond_dim", "hbond"))
        out_name = str(params.get("output", "hbonds"))
        labels = {}
        for index, row in enumerate(rows):
            donor = row["donor"]
            acceptor = row["acceptor"]
            labels[f"{donor[0]}:{donor[2]}:{donor[3]}-{acceptor[0]}:{acceptor[2]}:{acceptor[3]}"] = index
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={out_dim: labels, "statistic": {"occupancy": 0, "mean_distance": 1, "mean_angle": 2}},
            info={
                "missing_code": np.nan,
                "n_frames": len(selected),
                "n_candidates": len(triples),
                "n_hbonds": len(rows),
                "cutoff": cutoff,
                "angle_cutoff": angle_cutoff,
                "min_occupancy": float(params.get("min_occupancy", 0.2)),
                "stride": stride,
            },
        )
        self._export_data = {"hbonds": len(rows), "n_candidates": len(triples), "n_frames": len(selected)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
