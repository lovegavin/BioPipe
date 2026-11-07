"""Detect helices from CA geometry and report pairwise axis angles and spacing."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.base import Step


def _column(form: Form, dim: str, name: str) -> np.ndarray:
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise StepError(f"structure_helix_helix_angle: the structure form has no '{name}' column")
    return np.take(form.data, int(labels[name]), axis=list(form.dims).index(dim))


def _text_column(form: Form, dim: str, name: str) -> np.ndarray:
    values = _column(form, dim, name)
    encoders = (form.info or {}).get("encoders") or {}
    table = encoders.get(dim) or {}
    encoder = table.get(name)
    if isinstance(encoder, LabelEncoder):
        return np.array(encoder.inverse_transform(values), dtype=object)
    return np.array([f"{value:g}" for value in values], dtype=object)


def ca_atoms(form: Form, atom_dim: str, field_dim: str) -> tuple[list[str], np.ndarray]:
    atom_names = _text_column(form, field_dim, "atom_name")
    chains = _text_column(form, field_dim, "chain")
    resnames = _text_column(form, field_dim, "resname")
    numbers = _column(form, field_dim, "residue_number")
    coords = np.column_stack([_column(form, field_dim, axis) for axis in ("x", "y", "z")])
    seen: dict[str, np.ndarray] = {}
    for index, name in enumerate(atom_names):
        if str(name).strip() != "CA":
            continue
        key = f"{chains[index]}:{resnames[index]}:{int(round(float(numbers[index])))}"
        if key not in seen:
            seen[key] = coords[index]
    if len(seen) < 4:
        raise StepError("structure_helix_helix_angle: at least four CA atoms are required")
    labels = list(seen)
    return labels, np.asarray([seen[label] for label in labels], dtype=np.float64)


def helix_runs(
    ca: np.ndarray,
    chains: list[str] | None = None,
    *,
    span: float = 3.9,
    wide: float = 6.2,
    min_residues: int = 4,
) -> list[list[int]]:
    """Detect helical runs inside each chain segment of the CA trace."""
    if chains is None:
        chains = ["A"] * len(ca)
    if len(chains) != len(ca):
        raise StepError("structure_helix_helix_angle: chain labels must match the CA count")
    segments: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(ca) + 1):
        if index == len(ca) or chains[index] != chains[start]:
            segments.append((start, index))
            start = index
    runs: list[list[int]] = []
    for seg_start, seg_end in segments:
        run_start: int | None = None
        for index in range(seg_start, seg_end - 1):
            step = float(np.linalg.norm(ca[index + 1] - ca[index]))
            if index + 3 < seg_end:
                wide_step = float(np.linalg.norm(ca[index + 3] - ca[index]))
            else:
                # The i..i+3 test is undefined at the chain end; trust the local step.
                wide_step = 0.0
            helical = step < span and wide_step < wide
            if helical and run_start is None:
                run_start = index
            if not helical and run_start is not None:
                run = list(range(run_start, index + 1))
                if len(run) >= min_residues:
                    runs.append(run)
                run_start = None
        if run_start is not None:
            run = list(range(run_start, seg_end))
            if len(run) >= min_residues:
                runs.append(run)
    return runs


def helix_axis(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    centre = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - centre)
    axis = vt[0] / np.linalg.norm(vt[0])
    projected = (points - centre) @ axis
    return centre, axis, float(projected.max() - projected.min())


def line_distance(p0: np.ndarray, d0: np.ndarray, p1: np.ndarray, d1: np.ndarray) -> float:
    cross = np.cross(d0, d1)
    norm = float(np.linalg.norm(cross))
    delta = p1 - p0
    # Near-parallel axes make the skew-line formula ill-conditioned (the cross
    # product is dominated by round-off), so fall back to the perpendicular
    # component of the centre offset in that regime.
    if norm < 1e-9 or abs(float(np.dot(d0, d1))) > 1.0 - 1e-6:
        direction = d0 if abs(float(np.dot(d0, d1))) <= 1.0 else d1
        return float(np.linalg.norm(delta - np.dot(delta, direction) * direction))
    return abs(float(np.dot(delta, cross)) / norm)


def pair_rows(ca: np.ndarray, labels: list[str], runs: list[list[int]], *, cutoff: float) -> list[list[float]]:
    rows: list[list[float]] = []
    for left in range(len(runs)):
        for right in range(left + 1, len(runs)):
            first = ca[runs[left]]
            second = ca[runs[right]]
            c0, d0, len0 = helix_axis(first)
            c1, d1, len1 = helix_axis(second)
            angle = float(np.degrees(np.arccos(min(1.0, abs(float(np.dot(d0, d1)))))))
            distance = line_distance(c0, d0, c1, d1)
            spans = [float(np.linalg.norm(ca[a] - ca[b])) for a in runs[left] for b in runs[right]]
            contacts = sum(1 for value in spans if value <= cutoff)
            rows.append(
                [
                    float(angle),
                    float(distance),
                    float(min(spans)) if spans else 0.0,
                    float(contacts),
                    float(len0),
                    float(len1),
                ]
            )
    return rows


class StructureHelixHelixAngleStep(Step):
    provider = "operon-core"
    parameters_file = "structure_helix_helix_angle.StructureHelixHelixAngleStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "structure_helix_helix_angle",
        "kind": "operator",
        "title": "Helix-helix angle and spacing",
        "description": "Detect helical runs from CA geometry and report pairwise axis angles, axis distances and inter-helix contact counts.",
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim", "default": "atom"}, {"param": "field_dim", "default": "field"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("structure_helix_helix_angle: a PDB form input is required")
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim", "atom") or "atom")
        field_dim = str(ctx.step_params.get("field_dim", "field") or "field")
        residue_dim = str(ctx.step_params.get("residue_dim", "helix_pair") or "helix_pair")
        out_name = ctx.step_params.get("output", "helix_pairs") or "helix_pairs"
        cutoff = ctx.step_params.get("cutoff", 8.0)
        min_residues = ctx.step_params.get("min_residues", 4)

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_helix_helix_angle: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )
        if not isinstance(cutoff, (int, float)) or not 3.0 <= float(cutoff) <= 20.0:
            raise StepError("structure_helix_helix_angle: cutoff must be between 3 and 20 angstrom")
        if not isinstance(min_residues, int) or min_residues < 3:
            raise StepError("structure_helix_helix_angle: min_residues must be at least 3")

        labels, ca = ca_atoms(form, atom_dim, field_dim)
        chains = [label.split(":")[0] for label in labels]
        runs = helix_runs(ca, chains, min_residues=min_residues)
        if len(runs) < 2:
            raise StepError(
                f"structure_helix_helix_angle: at least two helices of {min_residues} residues are required, "
                f"found {len(runs)}"
            )
        rows = pair_rows(ca, labels, runs, cutoff=float(cutoff))
        codes = np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, 6), dtype=np.float32)
        labels_map = {
            residue_dim: {f"helix{i + 1}-helix{j + 1}": k for k, (i, j) in enumerate(
                (a, b) for a in range(len(runs)) for b in range(a + 1, len(runs))
            )},
            "statistic": {
                "angle_deg": 0,
                "axis_distance": 1,
                "min_ca_distance": 2,
                "n_contacts": 3,
                "helix_i_residues": 4,
                "helix_j_residues": 5,
            },
        }
        out = Form(
            data=codes,
            dims=[residue_dim, "statistic"],
            labels=labels_map,
            info={
                "missing_code": np.nan,
                "helices": [{"index": index + 1, "start": labels[run[0]], "end": labels[run[-1]], "n_residues": len(run)} for index, run in enumerate(runs)],
                "cutoff": float(cutoff),
                "min_residues": int(min_residues),
                "unit": "angstrom",
                "n_helices": len(runs),
                "n_pairs": len(rows),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_helices": len(runs),
            "n_pairs": len(rows),
            "cutoff": float(cutoff),
            "helices": [
                {"index": index + 1, "start": labels[run[0]], "end": labels[run[-1]], "n_residues": len(run)}
                for index, run in enumerate(runs)
            ],
        }
        print(f"[structure_helix_helix_angle] {len(runs)} helices, {len(rows)} pairs at cutoff {cutoff}")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
