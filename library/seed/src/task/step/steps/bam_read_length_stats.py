"""Distribution of query lengths in a BAM file."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step, Form
from src.task.context import Context

from ._bam_qc_utils import bam_path, read_length_histogram


class BamReadLengthStatsStep(Step):
    provider = "operon-core"
    parameters_file = "bam_read_length_stats.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "bam_read_length_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "BAM read length statistics",
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
        "description": "Histogram and summary statistics of primary mapped read lengths.",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return max(size // 4, 8 << 20), 1 << 20

    def run(self, ctx: Context, inputs) -> None:
        params = {**{"max_length": 1000, "max_records": 0, "output": ""}, **dict(ctx.step_params or {})}
        out_name = params["output"] or self.name
        max_length = int(params["max_length"])
        if max_length < 1:
            raise ValueError("max_length must be positive")
        path = bam_path(inputs[0], self.name)
        counts, n_reads, total_bases, min_length, max_seen, overflow = read_length_histogram(
            path, max_length=max_length, max_records=int(params["max_records"])
        )
        if n_reads == 0:
            raise ValueError(f"{self.name}: no primary mapped reads")
        rows = []
        labels = {}
        denominator = float(n_reads)
        for length in range(1, max_length + 1):
            count = int(counts[length])
            if count == 0:
                continue
            labels[str(length)] = len(rows)
            rows.append([float(count), count / denominator])
        if overflow:
            labels[f"{max_length}+"] = len(rows)
            rows.append([float(overflow), overflow / denominator])
        cumulative = np.cumsum(counts[1:])
        median_index = int(np.searchsorted(cumulative, (n_reads + 1) // 2))
        median = float(median_index + 1) if median_index < max_length else float(max_seen)
        info = {
            "n_reads": n_reads,
            "min_length": int(min_length or 0),
            "max_length": int(max_seen),
            "mean_length": total_bases / denominator,
            "median_length": median,
            "overflow_reads": overflow,
        }
        ctx[out_name] = Form(
            np.asarray(rows, dtype=float),
            dims=["read_length", "statistic"],
            labels={"read_length": labels, "statistic": {"n_reads": 0, "fraction": 1}},
            info=info,
        )

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        return {"n_reads": int(ctx[name].info["n_reads"]), "mean_length": ctx[name].info["mean_length"]}
