"""Pairwise evolutionary distances from an aligned sequence set."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._phylo_infer import aligned_sequences, distance_matrix, usable_columns


class PhyloDistanceMatrixStep(Step):
    provider = "operon-core"
    parameters_file = "phylo_distance_matrix.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_distance_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Phylogenetic distance matrix",
        "description": (
            "Compute pairwise p-distance, JC69 or K2P distances from aligned "
            "sequences, with complete or pairwise gap deletion."
        ),
        "category": "Genome",
        "icon": "GitCompare",
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
            raise StepError("phylo_distance_matrix: an aligned sequence input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        model = str(params.get("model", "p")).strip().lower()
        deletion = str(params.get("deletion", "complete")).strip().lower()
        taxon_dim = str(params.get("taxon_dim", "taxon"))
        out_name = str(params.get("output", self.name))
        if model not in ("p", "jc69", "k2p", "protein"):
            raise StepError(f"phylo_distance_matrix: unknown model {model!r}")
        if deletion not in ("complete", "pairwise"):
            raise StepError(f"phylo_distance_matrix: unknown deletion mode {deletion!r}")

        records = aligned_sequences(inputs[0], sequence_dim, position_dim, "phylo_distance_matrix")
        if deletion == "complete":
            keep = usable_columns(records, model)
            if len(keep) < 3:
                raise StepError("phylo_distance_matrix: fewer than three comparable columns")
            records = [(name, "".join(seq[i] for i in keep)) for name, seq in records]
            sites = len(keep)
        else:
            sites = len(records[0][1])
        matrix = distance_matrix(records, model, deletion)
        names = [name for name, _ in records]
        labels = {name: index for index, name in enumerate(names)}
        out = Form(
            matrix.astype(np.float64),
            dims=[taxon_dim, f"{taxon_dim}_b"],
            labels={taxon_dim: labels, f"{taxon_dim}_b": dict(labels)},
            info={
                "model": model,
                "deletion": deletion,
                "n_sequences": len(names),
                "n_sites": sites,
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        off_diagonal = matrix[~np.eye(len(names), dtype=bool)]
        self._export_data = {
            "n_sequences": len(names),
            "model": model,
            "deletion": deletion,
            "n_sites": sites,
            "mean_distance": float(off_diagonal.mean()) if off_diagonal.size else 0.0,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
