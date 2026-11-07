# src/task/step/steps/genome_gene_density.py
"""Windowed gene density across every sequence of a GFF3/GTF annotation.

Input: Form from GffReader or GtfReader.
Output: 2D [window, statistic]

    window_start, window_end, n_features, features_per_kb,
    aligned_bp, aligned_fraction

``aligned_bp`` is the union of the selected feature intervals clipped to
the window, so overlapping genes are counted once.  ``genome_size`` per
sequence is the largest feature end (GFF files do not declare chromosome
length); the trailing partial window is therefore bounded by the last
annotated base, not by the true replicon end.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._annotation_utils import (
    annotation_table,
    merge_intervals,
    select_type,
    window_overlaps,
)


_STATISTICS = (
    "window_start",
    "window_end",
    "n_features",
    "features_per_kb",
    "aligned_bp",
    "aligned_fraction",
)


class GenomeGeneDensityStep(Step):
    """Gene (or CDS) density in fixed windows along each sequence."""

    provider = "operon-core"
    parameters_file = "genome_gene_density.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_gene_density",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Windowed gene density",
        "description": (
            "Count genes or CDS features per fixed window on every sequence "
            "and report the aligned fraction of each window."
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
                        {"param": "record_dim", "default": "record"},
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
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes)
        return max(size // 2, 8 * 2**20), 2 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        record_dim = str(params.get("record_dim", "record"))
        field_dim = str(params.get("field_dim", "field"))
        feature_type = str(params.get("feature_type", "gene")).strip() or "gene"
        window = int(params.get("window", 10000))
        out_name = str(params.get("output", self.name))
        if window < 1:
            raise StepError("genome_gene_density: window must be at least 1 bp")

        table = annotation_table(form, record_dim, field_dim, "genome_gene_density")
        chosen = select_type(table, feature_type, "genome_gene_density")
        seqids = [table["seqid"][i] for i in chosen]
        starts = table["start"][chosen]
        ends = table["end"][chosen]

        order = sorted(set(seqids))
        rows = []
        labels = []
        per_window_seqid = []
        genome_sizes = {}
        total_features = 0
        for seqid in order:
            mask = np.asarray([name == seqid for name in seqids], dtype=bool)
            seq_starts = starts[mask]
            seq_ends = ends[mask]
            if seq_starts.size == 0:
                continue
            limit = int(seq_ends.max())
            genome_sizes[seqid] = limit
            total_features += int(seq_starts.size)
            position = 1
            while position <= limit:
                window_end = min(position + window - 1, limit)
                hit = window_overlaps(seq_starts, seq_ends, position, window_end)
                n_features = int(hit.sum())
                clipped = [
                    (max(int(start), position), min(int(end), window_end))
                    for start, end in zip(seq_starts[hit], seq_ends[hit])
                ]
                aligned = sum(end - start + 1 for start, end in merge_intervals(clipped))
                span = window_end - position + 1
                rows.append(
                    [
                        position,
                        window_end,
                        n_features,
                        n_features * 1000.0 / span,
                        aligned,
                        aligned / span,
                    ]
                )
                labels.append(f"{seqid}:{position}-{window_end}")
                per_window_seqid.append(seqid)
                position = window_end + 1

        data = np.asarray(rows, dtype=np.float32).reshape(-1, len(_STATISTICS))
        out = Form(
            data=data,
            dims=["window", "statistic"],
            labels={
                "window": {label: index for index, label in enumerate(labels)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "feature_type": feature_type,
                "window": window,
                "seqid": per_window_seqid,
                "genome_sizes": genome_sizes,
                "n_windows": len(labels),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "windows": len(labels),
            "features": total_features,
            "genome_sizes": genome_sizes,
            "window": window,
            "feature_type": feature_type,
        }
        print(
            f"genome_gene_density: {len(labels)} windows over "
            f"{len(genome_sizes)} sequence(s), {total_features} {feature_type} records"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
