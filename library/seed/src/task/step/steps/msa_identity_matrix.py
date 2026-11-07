"""Pairwise identity matrix for aligned sequences."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._msa_utils import alignment_records, identity_matrix


class MsaIdentityMatrixStep(Step):
    provider = "operon-core"
    parameters_file = "msa_identity_matrix.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "msa_identity_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Alignment identity matrix",
        "description": (
            "Compute pairwise sequence identity over columns where both "
            "sequences have a residue (gaps ignored), returning a square matrix."
        ),
        "category": "Sequence",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("msa_identity_matrix: an alignment input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        taxon_dim = str(params.get("taxon_dim", "taxon"))
        out_name = str(params.get("output", self.name))

        names, sequences = alignment_records(
            inputs[0], sequence_dim, position_dim, "msa_identity_matrix"
        )
        matrix, comparable = identity_matrix(sequences)
        labels = {name: index for index, name in enumerate(names)}
        form = Form(
            matrix,
            dims=[taxon_dim, f"{taxon_dim}_b"],
            labels={taxon_dim: labels, f"{taxon_dim}_b": dict(labels)},
            info={
                "n_sequences": len(names),
                "n_columns": len(sequences[0]),
                "comparable_pairs_min": int(comparable[np.triu_indices(len(names), 1)].min())
                if len(names) > 1
                else 0,
            },
        )
        form.validate()
        ctx[out_name] = form
        off_diagonal = matrix[~np.eye(len(names), dtype=bool)]
        self._export_data = {
            "n_sequences": len(names),
            "n_columns": len(sequences[0]),
            "min_identity": float(off_diagonal.min()) if off_diagonal.size else 1.0,
            "mean_identity": float(off_diagonal.mean()) if off_diagonal.size else 1.0,
            "max_identity": float(off_diagonal.max()) if off_diagonal.size else 1.0,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
