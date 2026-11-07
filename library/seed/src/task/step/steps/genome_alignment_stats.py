"""Pairwise genome alignment statistics derived from minimap2 PAF records."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.core import StepError
from src.task.step.base import Step, Form

from ._genome_align_utils import alignment_statistics, run_minimap2, write_fasta

_LABELS = [
    "n_alignments",
    "aligned_bp",
    "query_bp_covered",
    "reference_bp_covered",
    "query_coverage",
    "reference_coverage",
    "mean_identity",
    "max_alignment_bp",
    "n50_alignment_bp",
]


class GenomeAlignmentStatsStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "id": "genome_alignment_stats",
        "title": "Genome alignment statistics",
        "version": "1.0.0",
        "protocol_version": 3,
        "kind": "operator",
        "category": "Genome",
        "icon": "GitCompare",
        "description": "Align two assemblies with minimap2 and summarise aligned bases, coverage and identity.",
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

    parameters_file = "genome_alignment_stats.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 2, 32 * 2 ** 20), 4 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        preset = str(params.get("preset", "asm5"))
        min_block = int(params.get("min_block", 1000))
        min_identity = float(params.get("min_identity", 0.0))
        threads = int(params.get("threads", 1))
        timeout = int(params.get("timeout_seconds", 1800))
        binary = str(params.get("minimap2_path", "minimap2"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        value_dim = str(params.get("value_dim", "value"))
        out_name = str(params.get("output", "stats"))

        temporary = Path(tempfile.mkdtemp(prefix="operon_genome_align_"))
        try:
            query_path = temporary / "query.fasta"
            reference_path = temporary / "reference.fasta"
            write_fasta(inputs[0], str(params.get("query_sequence_dim", "sequence")),
                        str(params.get("query_position_dim", "position")), query_path, "genome_alignment_stats")
            write_fasta(inputs[1], str(params.get("reference_sequence_dim", "sequence")),
                        str(params.get("reference_position_dim", "position")), reference_path, "genome_alignment_stats")
            query_length = sum(len(line.strip()) for line in query_path.read_text(encoding="utf-8").splitlines()
                               if line and not line.startswith(">"))
            reference_length = sum(len(line.strip()) for line in reference_path.read_text(encoding="utf-8").splitlines()
                                   if line and not line.startswith(">"))
            records = run_minimap2(query_path, reference_path, preset, threads, timeout, binary)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

        statistics = alignment_statistics(records, query_length, reference_length, min_block, min_identity)
        values = [[float(statistics[label])] for label in _LABELS]
        out = Form(
            np.asarray(values, dtype=np.float64),
            dims=[statistic_dim, value_dim],
            labels={statistic_dim: {label: index for index, label in enumerate(_LABELS)},
                    value_dim: {"value": 0}},
            info=dict(statistics),
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = dict(statistics)

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))


__all__ = ["GenomeAlignmentStatsStep"]
