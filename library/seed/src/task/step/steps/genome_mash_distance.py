# src/task/step/steps/genome_mash_distance.py
"""Mash distance and ANI from exact canonical k-mer Jaccard."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._kmer_utils import mash_distance, unique_kmers


class GenomeMashDistanceStep(Step):
    """Mash distance/ANI computed from the exact k-mer Jaccard index."""

    provider = "operon-core"
    parameters_file = "genome_mash_distance.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_mash_distance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Mash distance and ANI",
        "description": (
            "Compute the Mash distance and average nucleotide identity from "
            "the exact canonical k-mer Jaccard index of two genomes."
        ),
        "category": "Genome",
        "icon": "GitCompare",
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
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "encoders": {"type": "object", "optional": True},
                    },
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                },
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
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes)
        return max(size * 5, 64 * 2**20), 8 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs[0], inputs[1]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        k = int(params.get("k", 21))
        out_name = str(params.get("output", self.name))
        if k < 3 or k > 31:
            raise StepError("genome_mash_distance: k must be between 3 and 31")

        names_a, kmers_a = unique_kmers(
            first, sequence_dim, position_dim, k, "genome_mash_distance"
        )
        names_b, kmers_b = unique_kmers(
            second, sequence_dim, position_dim, k, "genome_mash_distance"
        )
        intersection = int(np.intersect1d(kmers_a, kmers_b, assume_unique=True).size)
        union = int(kmers_a.size + kmers_b.size - intersection)
        jaccard = float(intersection) / float(union) if union else 1.0
        distance = mash_distance(jaccard, k)
        shared = intersection
        labels = [
            "jaccard",
            "distance",
            "ani",
            "shared_kmers",
            "n_kmers_a",
            "n_kmers_b",
            "k",
        ]
        values = [
            jaccard,
            distance,
            1.0 - distance,
            float(shared),
            float(kmers_a.size),
            float(kmers_b.size),
            float(k),
        ]
        data = np.asarray([[value] for value in values], dtype=np.float64)
        out = Form(
            data=data,
            dims=["statistic", "value"],
            labels={
                "statistic": {label: index for index, label in enumerate(labels)},
                "value": {"value": 0},
            },
            info={
                "k": k,
                "sequences_a": len(names_a),
                "sequences_b": len(names_b),
                "formula": "-ln(2j/(1+j))/k",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "k": k,
            "jaccard": jaccard,
            "distance": distance,
            "ani": 1.0 - distance,
            "shared_kmers": shared,
        }
        print(
            f"genome_mash_distance: ANI {1.0 - distance:.6f}, "
            f"distance {distance:.6f} (Jaccard {jaccard:.6f})"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
