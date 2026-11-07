"""Per-residue B-factor profiles for structure quality control."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, heavy_atom_mask, residue_labels

_STATISTICS = ("mean_bfactor", "max_bfactor", "n_atoms")


def column(form: Form, field_dim: str, name: str) -> np.ndarray:
    """Return one numeric or decoded string column from a PDB-style form."""
    fields = list(form.dims)
    if len(fields) != 2 or field_dim not in fields:
        raise StepError("structure_bfactor_profile: the structure form must have two dims")
    index = fields.index(field_dim)
    if name not in form.labels.get(field_dim, {}):
        raise StepError(f"structure_bfactor_profile: the structure form has no '{name}' column")
    position = form.labels[field_dim][name]
    values = form.data.take(position, axis=index)
    return values


def numeric_column(form: Form, field_dim: str, name: str) -> np.ndarray:
    values = column(form, field_dim, name)
    if values.dtype.kind in "OUS":
        return np.asarray([float(value) for value in values], dtype=np.float64)
    return np.asarray(values, dtype=np.float64)


def residue_profile(form: Form, field_dim: str, exclude: set[str]) -> list[tuple[str, float, float, int]]:
    """Aggregate B-factors per residue for the heavy atoms that survive the filter."""
    bfactors = numeric_column(form, field_dim, "bfactor")
    labels = residue_labels(form, field_dim)
    resnames = decode_column(form, field_dim, "resname")
    heavy = heavy_atom_mask(form, field_dim)
    keep = heavy & np.asarray([resname.strip().upper() not in exclude for resname in resnames])
    order: list[str] = []
    grouped: dict[str, list[float]] = {}
    for index in np.flatnonzero(keep):
        label = labels[index]
        if label not in grouped:
            order.append(label)
            grouped[label] = []
        grouped[label].append(float(bfactors[index]))
    return [(label, float(np.mean(grouped[label])), float(np.max(grouped[label])), len(grouped[label])) for label in order]


class StructureBfactorProfileStep(Step):
    provider = "operon-core"
    parameters_file = "structure_bfactor_profile.StructureBfactorProfileStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_bfactor_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure B-factor Profile",
        "description": (
            "Summarise crystallographic B-factors per residue (mean, maximum, atom count) "
            "with heavy-atom filtering, order residues from most to least flexible, and "
            "report the global distribution for design and model quality control."
        ),
        "category": "Machine Learning",
        "icon": "ChartBar",
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
                    "info": {"encoders": {"type": "object", "optional": True}},
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
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        form = inputs[0] if inputs else None
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        residue_dim = str(params.get("residue_dim", "residue"))
        output = str(params.get("output", "output"))
        if form is None or len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_bfactor_profile: a structure form with dims [{atom_dim}, {field_dim}] is required"
            )
        exclude_text = str(params.get("exclude_resnames", "HOH,WAT"))
        exclude = {token.strip().upper() for token in exclude_text.replace(";", ",").split(",") if token.strip()}
        rows = residue_profile(form, field_dim, exclude)
        if not rows:
            raise StepError(
                "structure_bfactor_profile: the structure has no heavy atoms to profile"
            )
        ordered = sorted(rows, key=lambda row: (-row[1], row[0]))
        data = np.asarray([row[1:] for row in ordered], dtype=np.float32)
        values = np.asarray([row[1] for row in ordered], dtype=np.float64)
        labels = [row[0] for row in ordered]
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_residues": len(ordered),
                "global_mean": float(np.mean(values)),
                "global_median": float(np.median(values)),
                "global_std": float(np.std(values)),
                "units": "A^2",
                "excluded_resnames": sorted(exclude),
                "most_flexible": labels[:5],
                "least_flexible": labels[-5:],
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "residues": len(ordered),
            "global_mean": out.info["global_mean"],
            "global_median": out.info["global_median"],
            "most_flexible": labels[:5],
            "least_flexible": labels[-5:],
        }
        print(
            f"[structure_bfactor_profile] {len(ordered)} residues, "
            f"mean B {out.info['global_mean']:.2f}, most flexible {labels[0]}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
