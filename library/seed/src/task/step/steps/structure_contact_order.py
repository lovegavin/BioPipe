"""Absolute and relative contact order from CA contact pairs."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
)


def ca_coordinates(coords: np.ndarray, labels: list[str], names: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """Coordinates of the CA atom of every residue, in first-appearance order."""

    order: list[str] = []
    chosen: dict[str, int] = {}
    for index, label in enumerate(labels):
        if str(names[index]).strip().upper() != "CA":
            continue
        if label not in chosen:
            chosen[label] = index
            order.append(label)
    if not order:
        raise StepError("structure_contact_order: the structure form has no CA atoms")
    return np.asarray([coords[chosen[label]] for label in order], dtype=np.float64), order


def contact_pairs(ca: np.ndarray, cutoff: float, min_separation: int) -> list[tuple[int, int]]:
    """Residue index pairs closer than the cutoff and at least ``min_separation`` apart."""

    pairs: list[tuple[int, int]] = []
    count = len(ca)
    for left in range(count):
        deltas = ca - ca[left]
        distances = np.sqrt(np.sum(deltas * deltas, axis=1))
        for right in np.flatnonzero(distances <= cutoff):
            right = int(right)
            if right > left and right - left >= min_separation:
                pairs.append((left, right))
    return pairs


def contact_order(ca: np.ndarray, cutoff: float, min_separation: int) -> tuple[dict, float, float, int]:
    """Per-residue contact counts, absolute and relative contact order."""

    pairs = contact_pairs(ca, cutoff, min_separation)
    count = len(ca)
    contacts = [0] * count
    totals = [0.0] * count
    separations = []
    for left, right in pairs:
        separation = right - left
        separations.append(separation)
        contacts[left] += 1
        contacts[right] += 1
        totals[left] += separation
        totals[right] += separation
    if not pairs:
        raise StepError(
            "structure_contact_order: no residue pair is within the cutoff; "
            "increase cutoff or lower min_separation"
        )
    mean_separation = float(np.mean(separations))
    absolute = mean_separation / count if count else 0.0
    relative = mean_separation
    rows = {
        "contacts": contacts,
        "mean_separation": [
            (totals[index] / contacts[index]) if contacts[index] else float("nan") for index in range(count)
        ],
    }
    return rows, absolute, relative, len(pairs)


class StructureContactOrderStep(Step):
    """Absolute and relative contact order of a single-chain structure."""

    provider = "operon-core"

    parameters_file = "structure_contact_order.StructureContactOrderStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_contact_order",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure contact order",
        "description": (
            "Compute the absolute and relative contact order of a protein from CA-CA contacts. "
            "Rows report per-residue contact counts and mean sequence separation; the info "
            "carries the absolute contact order (mean sequence separation divided by chain "
            "length) and the relative contact order."
        ),
        "category": "Machine Learning",
        "icon": "Ruler",
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
        residue_dim = str(params.get("residue_dim") or "residue")
        cutoff = float(params.get("cutoff") if params.get("cutoff") is not None else 8.0)
        min_separation = int(
            params.get("min_separation") if params.get("min_separation") is not None else 3
        )
        out_name = str(params.get("output") or "contact_order")

        if len(inputs) != 1 or len(inputs[0].dims) != 2 or list(inputs[0].dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_contact_order: the input must have dims ["
                f"{atom_dim}, {field_dim}]"
            )
        if not 1.0 <= cutoff <= 20.0:
            raise StepError("structure_contact_order: cutoff must be between 1 and 20 angstrom")
        if min_separation < 1:
            raise StepError("structure_contact_order: min_separation must be at least 1")

        form = inputs[0]
        for name in ("x", "y", "z", "atom_name"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"structure_contact_order: the structure form has no '{name}' column"
                )

        coords = np.column_stack(
            [np.asarray(form.data[:, form.labels[field_dim][axis]], dtype=np.float64) for axis in ("x", "y", "z")]
        )
        labels = residue_labels(form, field_dim)
        names = decode_column(form, field_dim, "atom_name")
        heavy = heavy_atom_mask(form, field_dim)
        ca, residues = ca_coordinates(coords[heavy], labels, names)
        if len(residues) < 3:
            raise StepError(
                "structure_contact_order: at least three CA atoms are required for a contact order"
            )

        rows, absolute, relative, n_pairs = contact_order(ca, cutoff, min_separation)

        data = np.asarray(
            [
                [rows["contacts"][index], rows["mean_separation"][index]]
                for index in range(len(residues))
            ],
            dtype=np.float32,
        )
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: position for position, label in enumerate(residues)},
                "statistic": {"contact_count": 0, "mean_separation": 1},
            },
            info={
                "missing_code": float("nan"),
                "cutoff": cutoff,
                "min_separation": min_separation,
                "n_residues": len(residues),
                "n_contacts": n_pairs,
                "absolute_contact_order": absolute,
                "relative_contact_order": relative,
                "unit": "residues",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_residues": len(residues),
            "n_contacts": n_pairs,
            "absolute_contact_order": round(absolute, 6),
            "relative_contact_order": round(relative, 6),
            "cutoff": cutoff,
        }
        print(
            f"[structure_contact_order] {len(residues)} residues, {n_pairs} contacts, "
            f"relative contact order {relative:.4f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
