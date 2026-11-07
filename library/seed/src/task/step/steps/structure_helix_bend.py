"""Measure helix curvature from the CA trace."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from .structure_helix_helix_angle import ca_atoms, helix_runs


def direction_vectors(points: np.ndarray, window: int = 4) -> list[np.ndarray]:
    """Unit direction of every window of consecutive CA atoms."""
    directions: list[np.ndarray] = []
    for start in range(0, len(points) - window + 1):
        vector = points[start + window - 1] - points[start]
        norm = float(np.linalg.norm(vector))
        if norm > 0.0:
            directions.append(vector / norm)
    return directions


def bend_row(points: np.ndarray, window: int = 4) -> list[float]:
    """Return [n_residues, total_bend, max_local_bend, curvature_radius]."""
    directions = direction_vectors(points, window)
    if len(directions) < 2:
        raise StepError("structure_helix_bend: a helix needs at least two direction windows")
    local: list[float] = []
    for previous, current in zip(directions, directions[1:]):
        cosine = float(np.clip(np.dot(previous, current), -1.0, 1.0))
        local.append(float(np.degrees(np.arccos(cosine))))
    cosine = float(np.clip(np.dot(directions[0], directions[-1]), -1.0, 1.0))
    total = float(np.degrees(np.arccos(cosine)))
    arc_length = float(sum(np.linalg.norm(b - a) for a, b in zip(points, points[1:])))
    # Each window turns by (window - 1) residue steps, so the mean local turn
    # estimates the per-step turn; the whole trace turns that much per step.
    step_turn = float(np.mean(local))
    turned = step_turn * max(len(points) - 1, 1)
    if step_turn > 1e-6:
        radius = float(arc_length / np.radians(turned))
    elif total > 1e-6:
        radius = float(arc_length / np.radians(total))
    else:
        radius = float("inf")
    return [float(len(points)), total, float(max(local)), radius]


class StructureHelixBendStep(Step):
    provider = "operon-core"
    parameters_file = "structure_helix_bend.StructureHelixBendStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "structure_helix_bend",
        "kind": "operator",
        "title": "Helix axis bend",
        "description": "Fit helical runs from CA geometry and report the overall and local bend of each helix axis together with an approximate curvature radius.",
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

    _STATISTICS = ("n_residues", "total_bend_deg", "max_local_bend_deg", "curvature_radius")

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("structure_helix_bend: a PDB form input is required")
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim", "atom") or "atom")
        field_dim = str(ctx.step_params.get("field_dim", "field") or "field")
        helix_dim = str(ctx.step_params.get("helix_dim", "helix") or "helix")
        out_name = ctx.step_params.get("output", "bends") or "bends"
        window = ctx.step_params.get("window", 4)
        min_residues = ctx.step_params.get("min_residues", 4)

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_helix_bend: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )
        if isinstance(window, bool) or not isinstance(window, int) or not 3 <= window <= 12:
            raise StepError("structure_helix_bend: window must be an integer between 3 and 12")
        if isinstance(min_residues, bool) or not isinstance(min_residues, int) or min_residues < 4:
            raise StepError("structure_helix_bend: min_residues must be an integer of at least 4")

        labels, ca = ca_atoms(form, atom_dim, field_dim)
        chains = [label.split(":")[0] for label in labels]
        runs = helix_runs(ca, chains, min_residues=min_residues)
        if not runs:
            raise StepError("structure_helix_bend: no helical run with at least four residues was found")

        rows: list[list[float]] = []
        row_labels: list[str] = []
        for number, run in enumerate(runs, start=1):
            points = ca[run]
            try:
                row = bend_row(points, window)
            except StepError:
                continue
            rows.append(row)
            row_labels.append(f"helix{number}:{labels[run[0]]}-{labels[run[-1]]}")

        if not rows:
            raise StepError("structure_helix_bend: no helix is long enough for the requested window")

        matrix = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=matrix,
            dims=[helix_dim, "statistic"],
            labels={
                helix_dim: {label: index for index, label in enumerate(row_labels)},
                "statistic": {name: index for index, name in enumerate(self._STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_helices": len(row_labels),
                "window": window,
                "min_residues": min_residues,
                "statistics": list(self._STATISTICS),
                "helices": row_labels,
                "runs": runs,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_helices": len(row_labels),
            "window": window,
            "helices": row_labels,
            "max_total_bend_deg": float(np.max(matrix[:, 1])),
            "mean_total_bend_deg": float(np.mean(matrix[:, 1])),
        }
        print(f"[structure_helix_bend] {len(row_labels)} helices, window {window}")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
