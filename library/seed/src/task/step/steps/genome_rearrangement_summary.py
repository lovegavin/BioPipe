"""Rearrangement summary derived from collinear synteny blocks."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.task.step.base import Step, Form

from ._genome_align_utils import chain_blocks, rearrangement_summary, run_minimap2, write_fasta

_LABELS = [
    "n_blocks",
    "n_forward_blocks",
    "n_reverse_blocks",
    "n_breakpoints",
    "n_inversions",
    "n_translocations",
    "syntenic_fraction",
    "largest_block_bp",
    "largest_block_fraction",
    "total_block_bp",
]


class GenomeRearrangementSummaryStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "id": "genome_rearrangement_summary",
        "title": "Genome rearrangement summary",
        "version": "1.0.0",
        "protocol_version": 3,
        "kind": "operator",
        "category": "Genome",
        "icon": "ArrowsSplit",
        "description": "Summarise inversions, translocations and breakpoints from synteny blocks.",
        "outputs": [],
        "output_parameter": "output",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "fields": {"sequence": {"param": "query_sequence_dim", "default": "sequence"},
                                          "position": {"param": "query_position_dim", "default": "position"}}},
                {"version": 1, "fields": {"sequence": {"param": "reference_sequence_dim", "default": "sequence"},
                                          "position": {"param": "reference_position_dim", "default": "position"}}},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "dims": [{"param": "statistic_dim", "default": "statistic"},
                             {"param": "value_dim", "default": "value"}],
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "external_tools": ["minimap2"]},
        "inputs_arity": 2,
    }

    parameters_file = "genome_rearrangement_summary.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 2, 32 * 2 ** 20), 4 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        preset = str(params.get("preset", "asm5"))
        min_block = int(params.get("min_block", 1000))
        min_identity = float(params.get("min_identity", 0.0))
        max_ref_gap = int(params.get("max_reference_gap", 50000))
        threads = int(params.get("threads", 1))
        timeout = int(params.get("timeout_seconds", 1800))
        binary = str(params.get("minimap2_path", "minimap2"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        value_dim = str(params.get("value_dim", "value"))
        out_name = str(params.get("output", "summary"))

        temporary = Path(tempfile.mkdtemp(prefix="operon_genome_rearrangement_"))
        try:
            query_path = temporary / "query.fasta"
            reference_path = temporary / "reference.fasta"
            write_fasta(inputs[0], str(params.get("query_sequence_dim", "sequence")),
                        str(params.get("query_position_dim", "position")), query_path, "genome_rearrangement_summary")
            write_fasta(inputs[1], str(params.get("reference_sequence_dim", "sequence")),
                        str(params.get("reference_position_dim", "position")), reference_path, "genome_rearrangement_summary")
            records = run_minimap2(query_path, reference_path, preset, threads, timeout, binary)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

        records = [record for record in records
                   if record["block_length"] >= min_block and record["identity"] >= min_identity]
        blocks = chain_blocks(records, min_block, 2000, max_ref_gap)
        summary = rearrangement_summary(blocks)
        values = [[float(summary[label])] for label in _LABELS]
        out = Form(
            np.asarray(values, dtype=np.float64),
            dims=[statistic_dim, value_dim],
            labels={statistic_dim: {label: index for index, label in enumerate(_LABELS)},
                    value_dim: {"value": 0}},
            info=dict(summary),
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(summary)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))


__all__ = ["GenomeRearrangementSummaryStep"]
