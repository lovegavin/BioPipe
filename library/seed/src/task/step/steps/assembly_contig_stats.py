"""Per-contig assembly statistics from a FASTA assembly."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._assembly_utils import composition, contiguity, gap_runs, contig_records


class AssemblyContigStatsStep(Step):
    provider = "operon-core"
    parameters_file = "assembly_contig_stats.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_contig_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly contig statistics",
        "description": (
            "Compute length, GC fraction, N fraction and gap-run counts for "
            "every contig of a FASTA assembly."
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
            raise StepError("assembly_contig_stats: a FASTA input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        contig_dim = str(params.get("contig_dim", "contig"))
        out_name = str(params.get("output", self.name))

        records = contig_records(inputs[0], sequence_dim, position_dim, "assembly_contig_stats")
        stats = ["length", "gc_fraction", "n_fraction", "n_runs"]
        rows = []
        labels = {}
        for position, (name, sequence) in enumerate(records):
            gc, n_bases, length = composition(sequence)
            runs = gap_runs(sequence)
            labels[str(name)] = position
            rows.append(
                [
                    float(length),
                    float(gc) / length if length else 0.0,
                    float(n_bases) / length if length else 0.0,
                    float(len(runs)),
                ]
            )
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(stats)))
        lengths = [int(row[0]) for row in rows]
        summary = contiguity(lengths)
        gc_total = sum(float(row[1]) * int(row[0]) for row in rows)
        total = int(summary["total_bp"])
        summary["gc_fraction"] = gc_total / total if total else 0.0
        summary["n_bases"] = int(sum(float(row[2]) * int(row[0]) for row in rows))
        summary["largest_contig"] = max(records, key=lambda item: len(item[1]))[0] if records else ""

        out = Form(
            data,
            dims=[contig_dim, "statistic"],
            labels={contig_dim: labels, "statistic": {name: index for index, name in enumerate(stats)}},
            info={"summary": summary, "n_contigs": len(records)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_contigs": len(records),
            "total_bp": total,
            "n50": int(summary["n50"]),
            "l50": int(summary["l50"]),
            "gc_fraction": summary["gc_fraction"],
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
