"""Three-state secondary structure from backbone dihedral angles."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, has_column, residue_labels


def dihedral(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
    """Dihedral angle in degrees, in the open interval (-180, 180]."""

    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2
    b1_norm = np.linalg.norm(b1)
    if b1_norm == 0:
        return float("nan")
    b1 = b1 / b1_norm
    projection0 = b0 - np.dot(b0, b1) * b1
    projection2 = b2 - np.dot(b2, b1) * b1
    if np.linalg.norm(projection0) == 0 or np.linalg.norm(projection2) == 0:
        return float("nan")
    x = np.dot(projection0, projection2)
    y = np.dot(np.cross(b1, projection0), projection2)
    return float(np.degrees(np.arctan2(y, x)))


def backbone_angles(
    coords: np.ndarray,
    labels: list[str],
    names: np.ndarray,
) -> tuple[list[str], np.ndarray]:
    """Per-residue (phi, psi) angles; NaN when an atom or neighbour is missing."""

    residues: list[str] = []
    positions: dict[str, dict[str, int]] = {}
    for index, label in enumerate(labels):
        atom = str(names[index]).strip().upper()
        if label not in positions:
            positions[label] = {}
            residues.append(label)
        if atom in {"N", "CA", "C", "O"} and atom not in positions[label]:
            positions[label][atom] = index

    angles = np.full((len(residues), 2), np.nan, dtype=np.float64)
    for position, label in enumerate(residues):
        atoms = positions[label]
        if all(atom in atoms for atom in ("N", "CA", "C")):
            n_atom, ca_atom, c_atom = atoms["N"], atoms["CA"], atoms["C"]
            if position > 0:
                previous = positions[residues[position - 1]]
                if "C" in previous:
                    angles[position, 0] = dihedral(
                        coords[previous["C"]], coords[n_atom], coords[ca_atom], coords[c_atom]
                    )
            if position + 1 < len(residues):
                following = positions[residues[position + 1]]
                if "N" in following:
                    angles[position, 1] = dihedral(
                        coords[n_atom], coords[ca_atom], coords[c_atom], coords[following["N"]]
                    )
    return residues, angles


def _in_helix(phi: float, psi: float) -> bool:
    return -100.0 <= phi <= -30.0 and -80.0 <= psi <= 10.0


def _in_strand(phi: float, psi: float) -> bool:
    if -170.0 <= phi <= -60.0:
        return 90.0 <= psi <= 180.0 or -180.0 <= psi <= -150.0
    return False


def assign_states(
    angles: np.ndarray,
    *,
    window: int = 5,
    min_helix_fraction: float = 0.6,
    min_strand_fraction: float = 0.5,
) -> list[str]:
    """Smoothed three-state assignment (H helik, E strand, C coil)."""

    count = len(angles)
    raw: list[str] = []
    for phi, psi in angles:
        if np.isfinite(phi) and np.isfinite(psi) and _in_helix(phi, psi):
            raw.append("H")
        elif np.isfinite(phi) and np.isfinite(psi) and _in_strand(phi, psi):
            raw.append("E")
        else:
            raw.append("C")

    half = window // 2
    states: list[str] = []
    for position in range(count):
        low = max(0, position - half)
        high = min(count, position + half + 1)
        chunk = raw[low:high]
        helix = chunk.count("H") / len(chunk)
        strand = chunk.count("E") / len(chunk)
        if helix >= min_helix_fraction:
            states.append("H")
        elif strand >= min_strand_fraction:
            states.append("E")
        else:
            states.append("C")

    smoothed = list(states)
    start = 0
    while start < count:
        stop = start
        while stop + 1 < count and states[stop + 1] == states[start]:
            stop += 1
        if states[start] != "C" and stop - start + 1 < window:
            for index in range(start, stop + 1):
                smoothed[index] = "C"
        start = stop + 1
    return smoothed


def segment_rows(states: list[str], residues: list[str]) -> list[dict]:
    """Contiguous segments of the same state, 1-based and inclusive."""

    rows: list[dict] = []
    start = 0
    while start < len(states):
        stop = start
        while stop + 1 < len(states) and states[stop + 1] == states[start]:
            stop += 1
        rows.append(
            {
                "state": states[start],
                "start": start + 1,
                "end": stop + 1,
                "length": stop - start + 1,
                "residues": residues[start : stop + 1],
            }
        )
        start = stop + 1
    return rows


class StructureSecondaryStructureStep(Step):
    """Approximate three-state secondary structure from phi/psi angles."""

    provider = "operon-core"

    parameters_file = "structure_secondary_structure.StructureSecondaryStructureStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_secondary_structure",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure secondary structure",
        "description": (
            "Assign a three-state secondary structure (helix H, strand E, coil C) from backbone "
            "phi/psi dihedral angles with a smoothing window. Rows are contiguous segments with "
            "their 1-based start, end and length; the per-residue string is stored in info."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        segment_dim = str(params.get("segment_dim") or "segment")
        window = int(params.get("window") if params.get("window") is not None else 5)
        helix_fraction = float(
            params.get("min_helix_fraction") if params.get("min_helix_fraction") is not None else 0.6
        )
        strand_fraction = float(
            params.get("min_strand_fraction") if params.get("min_strand_fraction") is not None else 0.5
        )
        out_name = str(params.get("output") or "segments")

        if len(inputs) != 1 or list(inputs[0].dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_secondary_structure: a structure form with dims "
                f"[{atom_dim}, {field_dim}] is required"
            )
        if not 1 <= window <= 21:
            raise StepError("structure_secondary_structure: window must be between 1 and 21 residues")
        if not 0.0 < helix_fraction <= 1.0:
            raise StepError(
                "structure_secondary_structure: min_helix_fraction must be in (0, 1]"
            )
        if not 0.0 < strand_fraction <= 1.0:
            raise StepError(
                "structure_secondary_structure: min_strand_fraction must be in (0, 1]"
            )

        form = inputs[0]
        for name in ("x", "y", "z", "atom_name"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"structure_secondary_structure: the structure form has no '{name}' column"
                )

        coords = np.column_stack(
            [
                np.asarray(form.data[:, form.labels[field_dim][axis]], dtype=np.float64)
                for axis in ("x", "y", "z")
            ]
        )
        labels = residue_labels(form, field_dim)
        names = decode_column(form, field_dim, "atom_name")
        residues, angles = backbone_angles(coords, labels, names)
        if len(residues) < 3:
            raise StepError(
                "structure_secondary_structure: at least three residues with backbone atoms are required"
            )

        states = assign_states(
            angles,
            window=window,
            min_helix_fraction=helix_fraction,
            min_strand_fraction=strand_fraction,
        )
        segments = segment_rows(states, residues)
        data = np.asarray(
            [[row["start"], row["end"], row["length"]] for row in segments], dtype=np.float32
        )
        out = Form(
            data=data,
            dims=[segment_dim, "statistic"],
            labels={
                segment_dim: {
                    f"{row['state']}{index + 1}": index for index, row in enumerate(segments)
                },
                "statistic": {"start": 0, "end": 1, "length": 2},
            },
            info={
                "missing_code": float("nan"),
                "method": "dihedral",
                "window": window,
                "min_helix_fraction": helix_fraction,
                "min_strand_fraction": strand_fraction,
                "residues": residues,
                "states": "".join(states),
                "segments": segments,
                "fractions": {
                    "helix": states.count("H") / len(states),
                    "strand": states.count("E") / len(states),
                    "coil": states.count("C") / len(states),
                },
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_residues": len(residues),
            "n_segments": len(segments),
            "states": "".join(states),
            "helix_fraction": round(states.count("H") / len(states), 6),
            "strand_fraction": round(states.count("E") / len(states), 6),
            "coil_fraction": round(states.count("C") / len(states), 6),
        }
        print(
            f"[structure_secondary_structure] {len(residues)} residues, {len(segments)} segments, "
            f"H {states.count('H')} E {states.count('E')} C {states.count('C')}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
