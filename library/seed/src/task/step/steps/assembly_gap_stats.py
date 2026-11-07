"""Gap statistics for a FASTA assembly."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._assembly_utils import contig_records, gap_runs


class AssemblyGapStatsStep(Step):
    provider = "operon-core"
    parameters_file = "assembly_gap_stats.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_gap_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly gap statistics",
        "description": (
            "Count N gaps, gap bases and the largest gap for every contig of a "
            "FASTA assembly, plus genome-wide gap totals."
        ),
        "category": "Genome",
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
        return max(size, 4 * 2**20), 2 * 2**20

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("assembly_gap_stats: a FASTA input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        contig_dim = str(params.get("contig_dim", "contig"))
        out_name = str(params.get("output", self.name))

        records = contig_records(inputs[0], sequence_dim, position_dim, "assembly_gap_stats")
        stats = ["n_gaps", "gap_bp", "largest_gap_bp"]
        rows = []
        labels = {}
        total_gap = 0
        total_bp = 0
        for position, (name, sequence) in enumerate(records):
            runs = gap_runs(sequence)
            sizes = [end - start for start, end in runs]
            labels[str(name)] = position
            rows.append([float(len(runs)), float(sum(sizes)), float(max(sizes) if sizes else 0)])
            total_gap += sum(sizes)
            total_bp += len(sequence)
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(stats)))
        info = {
            "n_contigs": len(records),
            "n_gaps": int(sum(row[0] for row in rows)),
            "total_gap_bp": int(total_gap),
            "total_bp": int(total_bp),
            "gap_fraction": (total_gap / total_bp) if total_bp else 0.0,
            "gaps_per_mb": (sum(row[0] for row in rows) / (total_bp / 1e6)) if total_bp else 0.0,
            "largest_gap_bp": int(max((row[2] for row in rows), default=0)),
        }
        out = Form(
            data,
            dims=[contig_dim, "statistic"],
            labels={contig_dim: labels, "statistic": {name: index for index, name in enumerate(stats)}},
            info={"summary": info},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(info)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
