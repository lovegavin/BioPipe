# src/task/step/steps/genome_kmer_spectrum.py
"""Canonical k-mer multiplicity spectrum for one or more genomes."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._kmer_utils import kmer_array, spectrum_histogram


class GenomeKmerSpectrumStep(Step):
    """Histogram of how many distinct canonical k-mers occur N times."""

    provider = "operon-core"
    parameters_file = "genome_kmer_spectrum.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_kmer_spectrum",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Genome k-mer spectrum",
        "description": (
            "Count canonical k-mers across a genome and report the "
            "multiplicity spectrum used to estimate genome size and repeats."
        ),
        "category": "Genome",
        "icon": "ChartBar",
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
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes)
        return max(size * 4, 32 * 2**20), 8 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        fasta = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        k = int(params.get("k", 21))
        max_frequency = int(params.get("max_frequency", 50))
        out_name = str(params.get("output", self.name))
        if k < 3 or k > 31:
            raise StepError("genome_kmer_spectrum: k must be between 3 and 31")
        if max_frequency < 1:
            raise StepError("genome_kmer_spectrum: max_frequency must be >= 1")

        names, values = kmer_array(
            fasta, sequence_dim, position_dim, k, "genome_kmer_spectrum"
        )
        histogram, distinct = spectrum_histogram(values, max_frequency)
        total_occurrences = int(values.size)
        if total_occurrences == 0 or distinct == 0:
            raise StepError("genome_kmer_spectrum: no valid k-mers")

        buckets = sorted(histogram)
        rows = []
        labels = []
        for bucket in buckets:
            label = str(bucket) if bucket <= max_frequency else f"{max_frequency}+"
            labels.append(label)
            rows.append(
                [float(histogram[bucket]), float(histogram[bucket]) / float(distinct)]
            )
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data=data,
            dims=["frequency", "statistic"],
            labels={
                "frequency": {label: index for index, label in enumerate(labels)},
                "statistic": {"n_kmers": 0, "fraction": 1},
            },
            info={
                "k": k,
                "sequences": len(names),
                "total_occurrences": total_occurrences,
                "distinct_kmers": distinct,
                "singletons": int(histogram.get(1, 0)),
                "max_frequency": max_frequency,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "k": k,
            "sequences": len(names),
            "total_occurrences": total_occurrences,
            "distinct_kmers": distinct,
            "singletons": int(histogram.get(1, 0)),
            "max_multiplicity": int(buckets[-1]) if buckets else 0,
        }
        print(
            f"genome_kmer_spectrum: {distinct} distinct {k}-mers, "
            f"{total_occurrences} occurrences"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
