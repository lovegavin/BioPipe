"""Druggability score for the largest buried cavity of a structure."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import decode_column, heavy_atom_mask, residue_labels
from ._structure_common import atom_coords, field_columns
from .interface_bsa import vdw_radii
from .sequence_hydrophobicity_profile import KYTE_DOOLITTLE
from .structure_cavity_lining import cavity_cells, lining_rows
from .structure_paratope_predict import _THREE_TO_ONE

_STATISTICS = ("volume", "n_lining", "hydrophobic_fraction", "enclosure", "druggability")


def hydrophobic_fraction(labels: list[str]) -> float:
    """Normalised Kyte-Doolittle mean over the lining residues."""

    values: list[float] = []
    for label in labels:
        parts = label.split(":")
        if len(parts) < 2:
            continue
        residue = _THREE_TO_ONE.get(parts[1], "")
        if residue in KYTE_DOOLITTLE:
            values.append((KYTE_DOOLITTLE[residue] + 4.5) / 9.0)
    if not values:
        return 0.0
    return float(np.clip(np.mean(values), 0.0, 1.0))


def enclosure_fraction(cells: list[tuple[int, int, int]]) -> float:
    """Fraction of the six grid neighbours of the cavity that are not cavity."""

    inside = set(cells)
    total = 0
    outside = 0
    for i, j, k in inside:
        for di, dj, dk in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            total += 1
            if (i + di, j + dj, k + dk) not in inside:
                outside += 1
    if not total:
        return 0.0
    return outside / total


def druggability_score(enclosure: float, hydrophobicity: float) -> float:
    """Combine enclosure and lining hydrophobicity into a 0-1 score."""

    return float(np.clip(0.6 * enclosure + 0.4 * hydrophobicity, 0.0, 1.0))


class StructureCavityDruggabilityStep(Step):
    """Score the largest cavity by enclosure and lining hydrophobicity."""

    provider = "operon-core"
    parameters_file = "structure_cavity_druggability.StructureCavityDruggabilityStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_cavity_druggability",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Cavity druggability",
        "description": (
            "Detect the largest buried cavity of a structure, measure how "
            "enclosed it is and how hydrophobic its lining is, and combine both "
            "into a 0-1 druggability score."
        ),
        "category": "Structure",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {"encoders": {"type": "object", "optional": True}},
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        residue_dim = str(params.get("residue_dim", "residue")).strip() or "residue"
        spacing = float(params.get("spacing") if params.get("spacing") is not None else 1.0)
        probe = float(params.get("probe_radius") if params.get("probe_radius") is not None else 1.4)
        min_volume = float(params.get("min_volume") if params.get("min_volume") is not None else 20.0)
        padding = float(params.get("padding") if params.get("padding") is not None else 2.0)
        lining_cutoff = float(
            params.get("lining_cutoff") if params.get("lining_cutoff") is not None else 4.0
        )
        out_name = params.get("output", self.name)

        if not 0.5 <= spacing <= 4.0:
            raise StepError("structure_cavity_druggability: spacing must be between 0.5 and 4.0")
        if not 0.5 <= probe <= 5.0:
            raise StepError("structure_cavity_druggability: probe_radius must be between 0.5 and 5.0")
        if min_volume <= 0:
            raise StepError("structure_cavity_druggability: min_volume must be positive")
        if not 1.0 <= lining_cutoff <= 8.0:
            raise StepError("structure_cavity_druggability: lining_cutoff must be between 1 and 8")

        form = inputs[0]
        field_columns(form, field_dim, ("x", "y", "z", "resname", "element", "residue_number", "chain"))
        heavy = heavy_atom_mask(form, field_dim)
        if not heavy.any():
            raise StepError("structure_cavity_druggability: the structure has no heavy atoms")
        coordinates = atom_coords(form, field_dim)[heavy]
        labels = residue_labels(form, field_dim)[heavy]
        decoded = decode_column(form, field_dim, "element")
        elements = np.asarray(
            [str(value).strip().upper() for value in decoded], dtype=object
        )[heavy]
        radii = vdw_radii(elements)
        try:
            components, centres, shape, _lo = cavity_cells(
                coordinates, radii, spacing=spacing, probe_radius=probe, padding=padding
            )
        except StepError as error:
            message = str(error)
            if message.startswith("structure_cavity_druggability"):
                raise
            raise StepError("structure_cavity_druggability: " + message) from error
        if not components:
            raise StepError("structure_cavity_druggability: no buried cavity was found")
        grid = centres.reshape(shape + (3,))
        best = max(components, key=lambda cells: len(cells))
        volume = len(best) * spacing**3
        if volume < min_volume:
            raise StepError(
                "structure_cavity_druggability: the largest cavity holds "
                f"{volume:.1f} A^3, below min_volume {min_volume:g}"
            )
        cavity_centres = np.asarray([grid[cell] for cell in best], dtype=np.float64)
        residue_coords: dict[str, list[list[float]]] = {}
        for label, coordinate in zip(labels, coordinates):
            residue_coords.setdefault(str(label), []).append(coordinate.tolist())
        aggregated = {label: np.asarray(points) for label, points in residue_coords.items()}
        rows = lining_rows(aggregated, cavity_centres, cutoff=lining_cutoff)
        if not rows:
            raise StepError(
                "structure_cavity_druggability: no residue lines the largest cavity"
            )
        lining_labels = [row[0] for row in rows]
        hydrophobicity = hydrophobic_fraction(lining_labels)
        enclosure = enclosure_fraction(best)
        score = druggability_score(enclosure, hydrophobicity)
        data = np.asarray(
            [[volume, float(len(rows)), hydrophobicity, enclosure, score]], dtype=np.float32
        )
        form_out = Form(
            data=data,
            dims=["cavity", "statistic"],
            labels={
                "cavity": {"largest": 0},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "volume": volume,
                "n_lining": len(rows),
                "hydrophobic_fraction": hydrophobicity,
                "enclosure": enclosure,
                "druggability": score,
                "lining_residues": lining_labels,
                "n_cavities": len(components),
                "spacing": spacing,
                "probe_radius": probe,
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "volume": volume,
            "n_lining": len(rows),
            "druggability": score,
            "hydrophobic_fraction": hydrophobicity,
            "enclosure": enclosure,
        }
        print(
            f"[{self.name}] cavity {volume:.1f} A^3, druggability {score:.3f} "
            f"({len(rows)} lining residue(s))"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
