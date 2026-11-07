"""Compact alignment summary for a BAM file."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step, Form
from src.task.context import Context

from ._bam_qc_utils import alignment_summary, bam_path, summarize

_LABELS = [
    "total_reads",
    "mapped_reads",
    "mapped_fraction",
    "unmapped_reads",
    "primary_reads",
    "secondary_reads",
    "supplementary_reads",
    "duplicate_reads",
    "duplicate_fraction",
    "paired_reads",
    "proper_pair_fraction",
    "reverse_fraction",
    "clipped_fraction",
    "mean_mapq",
    "clipped_bases_per_read",
    "references",
]


class BamAlignmentSummaryStep(Step):
    provider = "operon-core"
    parameters_file = "bam_alignment_summary.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "bam_alignment_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "BAM alignment summary",
        "category": "Quality Control",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "alignments",
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "labels": [],
                    "parallel": [],
                    "info": {"representation": {"type": "string", "enum": ["bam"]}},
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
        "description": "Read counts, mapping fractions, duplicates, pairing and clipping.",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return max(size // 4, 8 << 20), 1 << 20

    def run(self, ctx: Context, inputs) -> None:
        params = {**{"max_records": 0, "output": ""}, **dict(ctx.step_params or {})}
        out_name = params["output"] or self.name
        path = bam_path(inputs[0], self.name)
        summary = alignment_summary(path, max_records=int(params["max_records"]))
        values = summarize(summary)
        data = np.asarray([[float(values[label])] for label in _LABELS], dtype=float)
        labels = {label: index for index, label in enumerate(_LABELS)}
        ctx[out_name] = Form(
            data,
            dims=["statistic", "value"],
            labels={"statistic": labels, "value": {"value": 0}},
            info={"total_reads": values["total_reads"], "mapped_reads": values["mapped_reads"]},
        )

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        return {"total_reads": int(ctx[name].data[0][0]), "mapped_reads": int(ctx[name].data[1][0])}
