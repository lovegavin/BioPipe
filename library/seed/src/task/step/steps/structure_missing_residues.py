"""Internal numbering gaps of PDB polymer chains.

Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``.
Output: 2D Form ``[gap, statistic]`` with ``start``, ``end`` and ``n_missing``.

Only internal gaps are reported: a missing N-terminus or C-terminus cannot be
distinguished from a deliberately truncated construct in the coordinate file,
because ``PdbReader`` does not expose SEQRES records.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._structure_checks import chain_sequences, clean_residues, polymer_residues

_STATISTIC = {"start": 0, "end": 1, "n_missing": 2}


def missing_residue_rows(residues: list[dict]) -> tuple[list[dict], dict]:
    """Return one row per internal numbering gap plus per-chain spans."""
    rows: list[dict] = []
    spans: dict[str, dict] = {}
    for chain, sequence in chain_sequences(residues).items():
        spans[chain] = {
            "n_residues": len(sequence),
            "first": sequence[0]["number"],
            "last": sequence[-1]["number"],
        }
        for previous, following in zip(sequence, sequence[1:]):
            span = following["number"] - previous["number"]
            if span <= 1:
                continue
            start = previous["number"] + 1
            end = following["number"] - 1
            label = f"{chain}:{start}" if start == end else f"{chain}:{start}-{end}"
            rows.append(
                {
                    "label": label,
                    "chain": chain,
                    "start": start,
                    "end": end,
                    "n_missing": end - start + 1,
                }
            )
    return rows, spans


class StructureMissingResiduesStep(Step):
    """Count internal residue-number gaps for every polymer chain."""

    provider = "operon-core"
    parameters_file = "structure_missing_residues.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_missing_residues",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Missing residues between chain segments",
        "description": (
            "Detects internal gaps in the residue numbering of every polymer "
            "chain and reports the missing range and length. Terminal truncation "
            "is not detectable from the coordinate form."
        ),
        "category": "Structure",
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
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        gap_dim = str(params.get("gap_dim", "gap"))
        out_name = str(params.get("output", "missing_residues"))
        chain = str(params.get("chain", "")).strip()

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_missing_residues: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        residues = polymer_residues(form, atom_dim, field_dim)
        if not residues:
            raise StepError(
                "structure_missing_residues: no polymer residues with a CA atom were found"
            )
        residues = clean_residues(residues, chain, "structure_missing_residues")
        rows, spans = missing_residue_rows(residues)

        data = np.asarray(
            [[row["start"], row["end"], row["n_missing"]] for row in rows],
            dtype=np.float32,
        ).reshape(len(rows), 3)
        out = Form(
            data=data,
            dims=[gap_dim, "statistic"],
            labels={
                gap_dim: {row["label"]: index for index, row in enumerate(rows)},
                "statistic": dict(_STATISTIC),
            },
            info={
                "n_gaps": len(rows),
                "n_missing_total": int(sum(row["n_missing"] for row in rows)),
                "chains": list(spans),
                "spans": spans,
                "note": (
                    "internal numbering gaps only; terminal truncation is not "
                    "detectable from the coordinate form"
                ),
            },
        )
        out.validate()
        self._export_data = {
            "n_gaps": len(rows),
            "n_missing_total": int(sum(row["n_missing"] for row in rows)),
            "chains": list(spans),
            "gaps": [row["label"] for row in rows],
        }
        ctx[out_name] = out
        print(
            f"[structure_missing_residues] {len(rows)} gaps, "
            f"{self._export_data['n_missing_total']} missing residues across "
            f"{len(spans)} chains"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
