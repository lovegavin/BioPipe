"""MAPQ distribution of primary mapped alignments."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step, Form
from src.task.context import Context

from ._bam_qc_utils import bam_path, mapq_histogram, median_from_histogram


class BamMapqDistributionStep(Step):
    provider = "operon-core"
    parameters_file = "bam_mapq_distribution.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "bam_mapq_distribution",
        "version": "1.0.0",
        "kind": "operator",
        "title": "BAM MAPQ distribution",
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
        "description": "Histogram of mapping quality for primary mapped reads.",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return max(size // 4, 8 << 20), 1 << 20

    def run(self, ctx: Context, inputs) -> None:
        params = {**{"max_mapq": 60, "max_records": 0, "output": ""}, **dict(ctx.step_params or {})}
        out_name = params["output"] or self.name
        max_mapq = int(params["max_mapq"])
        if not 1 <= max_mapq <= 255:
            raise ValueError("max_mapq must be between 1 and 255")
        path = bam_path(inputs[0], self.name)
        counts, n_reads, total_mapq = mapq_histogram(
            path, max_mapq=max_mapq, max_records=int(params["max_records"])
        )
        denominator = n_reads if n_reads else 1
        data = np.column_stack([counts, counts / denominator]).astype(float)
        labels = {str(value): value for value in range(max_mapq + 1)}
        info = {
            "n_reads": n_reads,
            "max_mapq": max_mapq,
            "mean_mapq": total_mapq / denominator,
            "median_mapq": median_from_histogram(counts, n_reads),
            "pct_ge_20": float(counts[20:].sum() / denominator) if max_mapq >= 20 else 0.0,
            "pct_ge_30": float(counts[30:].sum() / denominator) if max_mapq >= 30 else 0.0,
        }
        ctx[out_name] = Form(
            data,
            dims=["mapq", "statistic"],
            labels={"mapq": labels, "statistic": {"n_reads": 0, "fraction": 1}},
            info=info,
        )

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        return {"n_reads": int(ctx[name].info["n_reads"])}
