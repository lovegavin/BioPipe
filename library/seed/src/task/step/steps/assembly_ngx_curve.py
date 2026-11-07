"""Assembly Nx curve."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._assembly_ngx_utils import contig_lengths, curve_rows
from ._assembly_utils import contig_records


class AssemblyNgxCurveStep(Step):
    id = "assembly_ngx_curve"
    provider = "operon-core"
    parameters_file = "assembly_ngx_curve.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_ngx_curve",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Assembly Nx curve",
        "description": "Compute the Nx curve (contig length threshold and cumulative coverage) for an assembly.",
        "provider": "operon-core",
        "category": "Genome",
        "icon": "TrendingUp",
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size, 8 * 2**20), 2**20

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = str(params.get("output", self.name))
        records = contig_records(
            inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")), self.id
        )
        lengths = contig_lengths(records)
        total = int(lengths.sum())
        genome_size = int(params.get("genome_size", 0)) or total
        if genome_size <= 0:
            raise StepError("assembly_ngx_curve: genome_size must be positive")
        try:
            step = int(params.get("step", 1))
        except (TypeError, ValueError) as exc:
            raise StepError("assembly_ngx_curve: step must be an integer") from exc
        if not 1 <= step <= 100:
            raise StepError("assembly_ngx_curve: step must be between 1 and 100")
        rows = curve_rows(lengths, genome_size, step)
        data = np.asarray([[row[1], row[2], row[3], row[4]] for row in rows], dtype=np.float64)
        labels = {f"{row[0]:g}": index for index, row in enumerate(rows)}
        out = Form(
            data,
            dims=["x", "statistic"],
            labels={
                "x": labels,
                "statistic": {
                    "threshold_length": 0,
                    "n_contigs_at_least": 1,
                    "assembly_fraction": 2,
                    "genome_fraction": 3,
                },
            },
            info={"genome_size": genome_size, "total_length": total, "n_contigs": int(lengths.size), "step": step},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "genome_size": genome_size,
            "total_length": total,
            "n_points": len(rows),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
