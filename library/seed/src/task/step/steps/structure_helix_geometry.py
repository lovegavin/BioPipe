"""Per-helix geometry from CA coordinates: rise, radius and residue twist."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

_STATISTICS = ("n_residues", "rise", "radius", "twist_deg", "residues_per_turn")
_STATISTIC = "statistic"


def ca_coordinates(form, field_dim: str, residue_dim: str) -> tuple[np.ndarray, list[str]]:
    """Return one CA coordinate per residue, in structure order."""
    from src.task.step.steps._protein_common import column_index, decode_column

    if len(form.dims) != 2:
        raise StepError("structure_helix_geometry: a structure form with two dimensions is required")
    if not hasattr(form, "info") or "atom_name" not in (form.info.get("fields") or []):
        pass
    try:
        names = decode_column(form, field_dim, "atom_name")
        residue_labels = decode_column(form, field_dim, "resname")
        numbers = decode_column(form, field_dim, "residue_number")
        chains = decode_column(form, field_dim, "chain")
    except StepError:
        raise StepError(
            "structure_helix_geometry: the PDB form needs atom_name, resname, residue_number and chain columns"
        )
    x = np.asarray(form.data[:, column_index(form, field_dim, "x")], dtype=np.float64)
    y = np.asarray(form.data[:, column_index(form, field_dim, "y")], dtype=np.float64)
    z = np.asarray(form.data[:, column_index(form, field_dim, "z")], dtype=np.float64)
    coords = np.column_stack([x, y, z])
    labels: list[str] = []
    points: list[list[float]] = []
    for index in range(coords.shape[0]):
        if str(names[index]).strip() != "CA":
            continue
        label = "{}:{}:{}".format(str(chains[index]).strip(), str(residue_labels[index]).strip(), str(numbers[index]).strip())
        if labels and labels[-1] == label:
            continue
        labels.append(label)
        points.append(coords[index].tolist())
    if len(labels) < 3:
        raise StepError("structure_helix_geometry: at least three CA atoms are required")
    return np.asarray(points, dtype=np.float64), labels


def helix_runs(ca: np.ndarray, *, ca_distance: float = 3.9, span_distance: float = 6.2, min_length: int = 4) -> list[tuple[int, int]]:
    """Return half-open [start, stop) runs classified as helices."""
    if ca_distance <= 0.0 or span_distance <= 0.0:
        raise StepError("structure_helix_geometry: distance thresholds must be positive")
    flags = np.zeros(ca.shape[0], dtype=bool)
    for index in range(ca.shape[0] - 3):
        step = float(np.linalg.norm(ca[index + 1] - ca[index]))
        span = float(np.linalg.norm(ca[index + 3] - ca[index]))
        contiguous = float(np.linalg.norm(ca[index + 2] - ca[index + 1]))
        if step < ca_distance and contiguous < ca_distance and span < span_distance:
            flags[index : index + 4] = True
    runs: list[tuple[int, int]] = []
    start = None
    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index
        if not flag and start is not None:
            if index - start >= min_length:
                runs.append((start, index))
            start = None
    if start is not None and flags.shape[0] - start >= min_length:
        runs.append((start, flags.shape[0]))
    return runs


def helix_geometry(points: np.ndarray) -> dict:
    """Rise, radius and twist of one helicoidal CA run."""
    if points.shape[0] < 4:
        raise StepError("structure_helix_geometry: a helix needs at least four CA atoms")
    centred = points - points.mean(axis=0, keepdims=True)
    _, _, vectors = np.linalg.svd(centred, full_matrices=False)
    axis = vectors[0]
    if axis.sum() < 0.0:
        axis = -axis
    projections = centred @ axis
    radial = centred - np.outer(projections, axis)
    radii = np.linalg.norm(radial, axis=1)
    steps = np.diff(projections)
    rise = float(np.mean(steps))
    twists = []
    for index in range(radial.shape[0] - 1):
        first = radial[index]
        second = radial[index + 1]
        denominator = np.linalg.norm(first) * np.linalg.norm(second)
        if denominator <= 0.0:
            continue
        cosine = float(np.clip(np.dot(first, second) / denominator, -1.0, 1.0))
        twists.append(np.degrees(np.arccos(cosine)))
    twist = float(np.mean(twists)) if twists else 0.0
    if not np.isfinite(rise) or not np.isfinite(twist):
        raise StepError("structure_helix_geometry: the helix geometry is not finite")
    per_turn = 360.0 / twist if twist > 0.0 else float("inf")
    return {
        "n_residues": int(points.shape[0]),
        "rise": rise,
        "radius": float(np.mean(radii)),
        "twist_deg": twist,
        "residues_per_turn": float(per_turn),
        "axis": axis,
    }


class StructureHelixGeometryStep(Step):
    """Measures rise, radius and twist for every helix in a structure."""

    provider = "operon-core"
    parameters_file = "structure_helix_geometry.StructureHelixGeometryStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_helix_geometry",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure Helix Geometry",
        "description": (
            "Detects CA helices and reports the geometric parameters of each one: axial rise "
            "per residue, helix radius, twist angle and residues per turn, which exposes "
            "over- or under-wound helical segments."
        ),
        "category": "Machine Learning",
        "icon": "Ruler",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (64 * 1024 * 1024, 0)

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        ca_distance = float(params.get("ca_distance", 3.9))
        span_distance = float(params.get("span_distance", 6.2))
        min_length = int(params.get("min_length", 4))
        if min_length < 4:
            raise StepError("structure_helix_geometry: min_length must be at least 4")
        if ca_distance <= 0.0 or span_distance <= 0.0:
            raise StepError("structure_helix_geometry: distance thresholds must be positive")
        ca, labels = ca_coordinates(inputs[0], field_dim, atom_dim)
        if list(inputs[0].dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_helix_geometry: the input must have dims [{}, {}], got {}".format(
                    atom_dim, field_dim, list(inputs[0].dims)
                )
            )
        runs = helix_runs(ca, ca_distance=ca_distance, span_distance=span_distance, min_length=min_length)
        rows = []
        helices = []
        for index, (start, stop) in enumerate(runs):
            geometry = helix_geometry(ca[start:stop])
            rows.append(
                [
                    geometry["n_residues"],
                    geometry["rise"],
                    geometry["radius"],
                    geometry["twist_deg"],
                    geometry["residues_per_turn"],
                ]
            )
            helices.append(
                {
                    "id": "helix{}".format(index + 1),
                    "start": labels[start],
                    "end": labels[stop - 1],
                    **{key: geometry[key] for key in _STATISTICS if key != "n_residues"},
                }
            )
        data = (
            np.asarray(rows, dtype=np.float32)
            if rows
            else np.zeros((0, len(_STATISTICS)), dtype=np.float32)
        )
        helix_dim = str(params.get("helix_dim", "helix"))
        output = Form(
            data=data,
            dims=[helix_dim, _STATISTIC],
            labels={
                helix_dim: {helix["id"]: index for index, helix in enumerate(helices)},
                _STATISTIC: {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "helices": helices,
                "n_helices": len(helices),
                "residues_in_helices": int(sum(row[0] for row in rows)),
                "n_residues": len(labels),
                "unit": "A",
            },
            axis_info={},
        )
        output.validate()
        output_name = str(params.get("output", "helices"))
        ctx[output_name] = output
        self._export_data = {
            "n_residues": len(labels),
            "n_helices": len(helices),
            "residues_in_helices": output.info["residues_in_helices"],
            "mean_rise": float(data[:, 1].mean()) if rows else 0.0,
            "mean_radius": float(data[:, 2].mean()) if rows else 0.0,
            "mean_twist": float(data[:, 3].mean()) if rows else 0.0,
        }
        print("[structure_helix_geometry] {} helices from {} residues".format(len(helices), len(labels)))

    def export(self, ctx) -> dict:
        return dict(getattr(self, "_export_data", {}))
