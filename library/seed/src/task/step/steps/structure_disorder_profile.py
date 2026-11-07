"""Per-residue structural disorder profile from B-factors and chain gaps.

Predicted and experimental structures both expose flexibility through the
B-factor column, and unmodelled stretches show up as numbering gaps.  The
operator combines both signals into a single per-residue disorder score so a
downstream filter can drop or flag flexible regions without another parser.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    residue_labels,
    residue_order,
)

_STATISTICS = ("mean_bfactor", "bfactor_z", "gap_to_next", "disorder_score")


def residue_table(form: Form, atom_dim: str, field_dim: str) -> list[dict]:
    """Return one record per residue with its mean B-factor."""

    if form.data.size == 0:
        raise StepError("structure_disorder_profile: the structure form is empty")
    bfactor = column_index(form, field_dim, "bfactor")
    if bfactor < 0:
        raise StepError(
            "structure_disorder_profile: the structure form carries no 'bfactor' column"
        )
    labels = residue_labels(form, field_dim)
    values = np.asarray(form.data, dtype=np.float64)[:, bfactor]
    order = residue_order(labels)
    records: list[dict] = []
    for label in order:
        mask = labels == label
        numbers = values[mask]
        numbers = numbers[np.isfinite(numbers)]
        if numbers.size == 0:
            continue
        chain, resname, number = str(label).split(":")
        digits = "".join(char for char in number if char.isdigit())
        if not digits:
            continue
        records.append(
            {
                "label": str(label),
                "chain": chain,
                "resname": resname,
                "number": int(digits),
                "mean_bfactor": float(numbers.mean()),
            }
        )
    if not records:
        raise StepError(
            "structure_disorder_profile: no residue carries a finite B-factor"
        )
    return records


def disorder_rows(records: list[dict], *, z_clip: float = 3.0) -> list[dict]:
    """Attach per-chain z-scores, numbering gaps and a disorder score."""

    by_chain: dict[str, list[dict]] = {}
    for record in records:
        by_chain.setdefault(record["chain"], []).append(record)

    rows: list[dict] = []
    for chain, chain_records in by_chain.items():
        chain_records.sort(key=lambda item: (item["number"], item["label"]))
        bfactors = np.array([item["mean_bfactor"] for item in chain_records])
        mean = float(bfactors.mean())
        std = float(bfactors.std())
        for index, record in enumerate(chain_records):
            gap = 0
            if index + 1 < len(chain_records):
                gap = max(chain_records[index + 1]["number"] - record["number"] - 1, 0)
            z = (record["mean_bfactor"] - mean) / std if std > 0 else 0.0
            z = float(np.clip(z, -float(z_clip), float(z_clip)))
            score = float(np.clip(0.5 * z, -1.0, 1.0)) + (0.5 if gap else 0.0)
            rows.append(
                {
                    "label": record["label"],
                    "chain": chain,
                    "number": record["number"],
                    "mean_bfactor": record["mean_bfactor"],
                    "bfactor_z": z,
                    "gap_to_next": gap,
                    "disorder_score": score,
                }
            )
    return rows


class StructureDisorderProfileStep(Step):
    """Flag flexible residues from B-factors and unmodelled chain gaps."""

    provider = "operon-core"
    parameters_file = (
        "structure_disorder_profile.StructureDisorderProfileStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_disorder_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure disorder profile",
        "description": (
            "Report one row per residue with the mean B-factor, its per-chain "
            "z-score, the number of unmodelled residues that follow it, and a "
            "combined disorder score."
        ),
        "category": "Structure",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "encoders": {"type": "object", "optional": True},
                    },
                    "dims": [
                        {"param": "atom_dim"},
                        {"param": "field_dim"},
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
        "dependencies": ["numpy>=1.24"],
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
        z_clip = float(params.get("z_clip", 3.0))
        out_name = str(params.get("output", "disorder")) or "disorder"

        if z_clip <= 0:
            raise StepError("structure_disorder_profile: z_clip must be positive")

        form = inputs[0]
        records = residue_table(form, atom_dim, field_dim)
        rows = disorder_rows(records, z_clip=z_clip)

        labels = {row["label"]: index for index, row in enumerate(rows)}
        if len(labels) != len(rows):
            raise StepError(
                "structure_disorder_profile: residue labels are not unique"
            )
        data = np.asarray(
            [
                [
                    row["mean_bfactor"],
                    row["bfactor_z"],
                    float(row["gap_to_next"]),
                    row["disorder_score"],
                ]
                for row in rows
            ],
            dtype=np.float32,
        )
        scores = data[:, 3]
        ctx[out_name] = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_residues": len(rows),
                "n_chains": int(len({row["chain"] for row in rows})),
                "missing_residues": int(sum(row["gap_to_next"] for row in rows)),
                "mean_disorder": float(scores.mean()) if scores.size else 0.0,
                "max_disorder": float(scores.max()) if scores.size else 0.0,
                "z_clip": z_clip,
            },
        )
        self._export_data = {
            "n_residues": len(rows),
            "n_chains": int(len({row["chain"] for row in rows})),
            "missing_residues": int(sum(row["gap_to_next"] for row in rows)),
            "mean_disorder": float(scores.mean()) if scores.size else 0.0,
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
