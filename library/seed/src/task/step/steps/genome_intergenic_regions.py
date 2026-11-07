# src/task/step/steps/genome_intergenic_regions.py
"""Intergenic regions left between annotated features on each sequence."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._annotation_utils import (
    annotation_table,
    complement_intervals,
    merge_intervals,
    select_type,
)


class GenomeIntergenicRegionsStep(Step):
    """Gaps between merged feature intervals, per sequence."""

    provider = "operon-core"
    parameters_file = "genome_intergenic_regions.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "genome_intergenic_regions",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Intergenic regions",
        "description": (
            "Merge genes (or CDS) on every sequence and report the regions "
            "between them, excluding the sequence ends."
        ),
        "category": "Genome",
        "icon": "Ruler",
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
        min_length = int(params.get("min_length", 0))
        out_name = str(params.get("output", self.name))
        if min_length < 0:
            raise StepError("genome_intergenic_regions: min_length must be >= 0")

        table = annotation_table(form, record_dim, field_dim, "genome_intergenic_regions")
        chosen = select_type(table, feature_type, "genome_intergenic_regions")
        seqids = [table["seqid"][i] for i in chosen]
        starts = table["start"][chosen]
        ends = table["end"][chosen]

        rows = []
        labels = []
        per_seqid = []
        genome_sizes = {}
        total_gap_bp = 0
        covered_bp = 0
        order = sorted(set(seqids))
        for seqid in order:
            mask = np.asarray([name == seqid for name in seqids], dtype=bool)
            if not mask.any():
                continue
            limit = int(ends[mask].max())
            genome_sizes[seqid] = limit
            merged = merge_intervals(zip(starts[mask], ends[mask]))
            covered_bp += sum(end - start + 1 for start, end in merged)
            for start, end in complement_intervals(merged, limit, min_length):
                gap = end - start + 1
                rows.append([gap])
                labels.append(f"{seqid}:{start}-{end}")
                per_seqid.append(seqid)
                total_gap_bp += gap

        data = np.asarray(rows, dtype=np.float32).reshape(-1, 1)
        out = Form(
            data=data,
            dims=["gap", "statistic"],
            labels={
                "gap": {label: index for index, label in enumerate(labels)},
                "statistic": {"gap_length": 0},
            },
            info={
                "missing_code": np.nan,
                "feature_type": feature_type,
                "seqid": per_seqid,
                "genome_sizes": genome_sizes,
                "n_gaps": len(labels),
                "total_gap_bp": total_gap_bp,
                "covered_bp": covered_bp,
                "min_length": min_length,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "gaps": len(labels),
            "total_gap_bp": total_gap_bp,
            "covered_bp": covered_bp,
            "feature_type": feature_type,
        }
        print(
            f"genome_intergenic_regions: {len(labels)} gaps, "
            f"{total_gap_bp} bp between {feature_type} features"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))

