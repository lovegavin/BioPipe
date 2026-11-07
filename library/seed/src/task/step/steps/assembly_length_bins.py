"""Contig length distribution bins."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._assembly_ngx_utils import bin_edges, bin_rows, contig_lengths
from ._assembly_utils import contig_records


class AssemblyLengthBinsStep(Step):
    id = "assembly_length_bins"
    provider = "operon-core"
    parameters_file = "assembly_length_bins.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "assembly_length_bins",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Contig length bins",
        "description": "Bin assembly contigs by length and report counts and bases per bin.",
        "provider": "operon-core",
        "category": "Genome",
        "icon": "BarChart3",
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
        edges = bin_edges(params.get("edges", "0,1000,5000,10000,0"))
        rows = bin_rows(lengths, edges)
        data = np.asarray([[row[1], row[2], row[3]] for row in rows], dtype=np.float64)
        labels = {row[0]: index for index, row in enumerate(rows)}
        out = Form(
            data,
            dims=["bin", "statistic"],
            labels={"bin": labels, "statistic": {"n_contigs": 0, "total_bp": 1, "max_length": 2}},
            info={"n_contigs": int(lengths.size), "total_bp": int(lengths.sum()), "edges": edges},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_contigs": int(lengths.size), "total_bp": int(lengths.sum())}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
