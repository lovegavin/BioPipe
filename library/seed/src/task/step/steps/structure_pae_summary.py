"""Per-residue summary of a predicted-alignment-error matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

_STATISTICS = ("mean_pae", "max_pae", "fraction_below")


class StructurePaeSummaryStep(Step):
    """Per-residue mean/max PAE and the fraction of residues below a threshold."""

    provider = "operon-core"

    parameters_file = "structure_pae_summary.StructurePaeSummaryStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_pae_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "PAE matrix summary",
        "description": (
            "Summarise an N x N predicted-alignment-error matrix (ColabFold, AlphaFold or "
            "ESMFold) into per-residue mean and maximum PAE plus the fraction of partner "
            "residues below a confidence threshold."
        ),
        "category": "Structure",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "row_dim"}, {"param": "col_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
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
        (form,) = inputs
        row_dim = str(params.get("row_dim") or "residue")
        col_dim = str(params.get("col_dim") or "residue_b")
        threshold = float(params.get("threshold") if params.get("threshold") is not None else 10.0)
        out_name = str(params.get("output") or "pae")

        if threshold <= 0:
            raise StepError("structure_pae_summary: threshold must be positive")
        if list(form.dims) != [row_dim, col_dim]:
            raise StepError(
                "structure_pae_summary: expected a PAE matrix with dims "
                f"[{row_dim}, {col_dim}], got {form.dims}"
            )
        matrix = np.asarray(form.data, dtype=np.float64)
        if matrix.ndim != 2:
            raise StepError(f"structure_pae_summary: expected a 2-D matrix, got shape {matrix.shape}")
        if matrix.size == 0:
            raise StepError("structure_pae_summary: the PAE matrix is empty")
        if matrix.shape[0] != matrix.shape[1]:
            raise StepError(
                f"structure_pae_summary: expected a square PAE matrix, got {matrix.shape[0]}x{matrix.shape[1]}"
            )
        if not np.isfinite(matrix).all():
            raise StepError("structure_pae_summary: the PAE matrix contains non-finite values")
        if float(matrix.min()) < 0:
            raise StepError("structure_pae_summary: the PAE matrix contains negative values")

        means = matrix.mean(axis=1)
        maximum = matrix.max(axis=1)
        fraction = (matrix < threshold).mean(axis=1)
        data = np.column_stack([means, maximum, fraction]).astype(np.float32)

        labels = _row_labels(form, row_dim, matrix.shape[0])
        out = Form(
            data=data,
            dims=["residue", "statistic"],
            labels={
                "residue": {label: index for index, label in enumerate(labels)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "mean_pae": float(means.mean()),
                "median_pae": float(np.median(means)),
                "max_pae": float(maximum.max()),
                "threshold": threshold,
                "n_residues": int(matrix.shape[0]),
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "mean_pae": float(means.mean()),
            "max_pae": float(maximum.max()),
            "threshold": threshold,
            "n_residues": int(matrix.shape[0]),
        }
        print(
            f"[structure_pae_summary] {matrix.shape[0]} residues, "
            f"mean PAE {means.mean():.2f}, {float(fraction.mean()):.1%} below {threshold:g}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


def _row_labels(form: Form, row_dim: str, count: int) -> list[str]:
    mapping = form.labels.get(row_dim) if isinstance(form.labels, dict) else None
    if isinstance(mapping, dict) and len(mapping) == count:
        return [label for label, _position in sorted(mapping.items(), key=lambda item: item[1])]
    return [f"residue{index + 1}" for index in range(count)]
