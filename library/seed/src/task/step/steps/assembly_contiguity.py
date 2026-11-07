"""Genome-assembly contiguity metrics from a per-contig statistics table."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._assembly_utils import contiguity


class AssemblyContiguityStep(Step):
    provider = "operon-core"
    parameters_file = "assembly_contiguity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_contiguity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly contiguity metrics",
        "description": (
            "Summarise N50/L50, N90/L90, auN, length distribution and weighted "
            "GC from an assembly contig table."
        ),
        "category": "Genome",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "contig_dim", "default": "contig"},
                        {"param": "statistic_dim", "default": "statistic"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
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
        return max(size, 2 * 2**20), 2**20

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("assembly_contiguity: a contig statistics table is required")
        form = inputs[0]
        params = ctx.step_params
        contig_dim = str(params.get("contig_dim", "contig"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        length_column = str(params.get("length_column", "length"))
        gc_column = str(params.get("gc_column", "gc_fraction"))
        out_name = str(params.get("output", self.name))

        if list(form.dims) != [contig_dim, statistic_dim]:
            raise StepError(
                f"assembly_contiguity: expected [{contig_dim}, {statistic_dim}], got {list(form.dims)}"
            )
        columns = form.labels.get(statistic_dim, {})
        if length_column not in columns:
            raise StepError(
                f"assembly_contiguity: missing '{length_column}' column; available {sorted(columns)}"
            )
        length_index = int(columns[length_column])
        lengths = [int(round(float(value))) for value in np.asarray(form.data)[:, length_index]]
        summary = contiguity(lengths)

        gc_index = int(columns[gc_column]) if gc_column in columns else None
        if gc_index is not None:
            weights = np.asarray(lengths, dtype=float)
            gc_values = np.asarray(form.data)[:, gc_index].astype(float)
            total = float(weights.sum())
            summary["gc_fraction"] = float((gc_values * weights).sum() / total) if total else 0.0

        contigs = form.labels.get(contig_dim, {})
        if contigs:
            ordered = sorted(contigs.items(), key=lambda item: item[1])
            largest_index = int(np.argmax(lengths))
            if largest_index < len(ordered):
                summary["largest_contig"] = ordered[largest_index][0]

        rows = [
            ("n_contigs", float(summary["n_contigs"])),
            ("total_bp", float(summary["total_bp"])),
            ("min_length", float(summary["min_length"])),
            ("mean_length", float(summary["mean_length"])),
            ("median_length", float(summary["median_length"])),
            ("max_length", float(summary["max_length"])),
            ("n50", float(summary["n50"])),
            ("l50", float(summary["l50"])),
            ("n90", float(summary["n90"])),
            ("l90", float(summary["l90"])),
            ("aun", float(summary["aun"])),
        ]
        if summary.get("gc_fraction") is not None:
            rows.append(("gc_fraction", float(summary["gc_fraction"])))
        data = np.asarray([[value] for _, value in rows], dtype=float)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info={"summary": summary},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {name: value for name, value in rows}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
