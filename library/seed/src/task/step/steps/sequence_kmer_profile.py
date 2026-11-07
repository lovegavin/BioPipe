"""K-mer composition and entropy profile for nucleotide or protein sequences."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

STATISTICS = (
    "entropy_1",
    "entropy_2",
    "entropy_k",
    "distinct_fraction_k",
    "top_kmer_frequency",
)


def kmer_counts(sequence: str, k: int) -> Counter:
    return Counter(sequence[index:index + k] for index in range(len(sequence) - k + 1))


def entropy(counts: Counter, total: int) -> float:
    if total <= 0:
        return 0.0
    return float(-sum((value / total) * math.log2(value / total) for value in counts.values()))


def kmer_row(sequence: str, k: int) -> dict:
    if k < 1:
        raise StepError("sequence_kmer_profile: k_mer must be at least 1")
    if len(sequence) < k:
        raise StepError(
            f"sequence_kmer_profile: a sequence of length {len(sequence)} is shorter than k_mer {k}"
        )
    counts_1 = kmer_counts(sequence, 1)
    counts_2 = kmer_counts(sequence, min(2, len(sequence)))
    counts_k = kmer_counts(sequence, k)
    total_k = sum(counts_k.values())
    top = max(counts_k.items(), key=lambda item: (item[1], item[0]))
    distinct = len(counts_k)
    return {
        "entropy_1": entropy(counts_1, sum(counts_1.values())),
        "entropy_2": entropy(counts_2, sum(counts_2.values())),
        "entropy_k": entropy(counts_k, total_k),
        "distinct_fraction_k": distinct / total_k if total_k else 0.0,
        "top_kmer_frequency": top[1] / total_k if total_k else 0.0,
        "_top_kmer": top[0],
        "_top_count": top[1],
        "_distinct": distinct,
        "_total": total_k,
    }


class SequenceKmerProfileStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_kmer_profile.SequenceKmerProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_kmer_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "K-mer composition profile",
        "description": "Summarises k-mer entropy, distinct fraction and the dominant k-mer per sequence.",
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "sequence_dim", "default": "sequence"},
                    {"param": "position_dim", "default": "position"},
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2,
                "info": {
                    "representation": {"type": "string", "const": "sequence_codes"},
                },
            }],
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
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        k = int(params.get("k_mer", 3))
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_kmer_profile: a sequence form with dims [{sequence_dim}, {position_dim}] "
                f"is required, got {list(form.dims)}"
            )

        sequences = [sequence for sequence in decode_sequences(form, sequence_dim, position_dim) if sequence]
        if not sequences:
            raise StepError("sequence_kmer_profile: the form contains no residues")

        rows = [kmer_row(sequence, k) for sequence in sequences]
        names = [str(label) for label in form.labels.get(sequence_dim, {})] or [
            f"seq{index + 1}" for index in range(len(rows))
        ]
        labels = {name: index for index, name in enumerate(names)}
        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        output = Form(
            data=data,
            dims=[sequence_dim, "statistic"],
            labels={sequence_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "k_mer": k,
                "sequences": [
                    {
                        "name": names[index],
                        "length": len(sequences[index]),
                        "top_kmer": row["_top_kmer"],
                        "top_count": row["_top_count"],
                        "distinct_kmers": row["_distinct"],
                        "total_kmers": row["_total"],
                    }
                    for index, row in enumerate(rows)
                ],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_sequences": len(rows),
            "k_mer": k,
            "mean_entropy_k": float(np.mean([row["entropy_k"] for row in rows])),
            "top_kmers": [row["_top_kmer"] for row in rows],
        }
        print(
            f"[sequence_kmer_profile] {len(rows)} sequences, k={k}, "
            f"mean entropy {self._export_data['mean_entropy_k']:.3f} bits"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
