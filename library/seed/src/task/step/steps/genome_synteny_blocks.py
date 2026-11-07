"""Collinear synteny blocks between two assemblies."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import numpy as np

from src.task.step.base import Step, Form

from ._genome_align_utils import chain_blocks, run_minimap2, write_fasta

_FIELDS = [
    "reference",
    "query",
    "ref_start",
    "ref_end",
    "query_start",
    "query_end",
    "strand",
    "n_alignments",
    "aligned_bp",
    "identity",
]


class GenomeSyntenyBlocksStep(Step):
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "id": "genome_synteny_blocks",
        "title": "Genome synteny blocks",
        "version": "1.0.0",
        "protocol_version": 3,
        "kind": "operator",
        "category": "Genome",
        "icon": "Route",
        "description": "Chain minimap2 alignments into collinear synteny blocks between two assemblies.",
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
                    "dims": [{"param": "block_dim", "default": "block"},
                             {"param": "field_dim", "default": "field"}],
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "external_tools": ["minimap2"]},
        "inputs_arity": 2,
    }

    parameters_file = "genome_synteny_blocks.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 2, 32 * 2 ** 20), 8 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        preset = str(params.get("preset", "asm5"))
        min_block = int(params.get("min_block", 1000))
        min_identity = float(params.get("min_identity", 0.0))
        max_ref_gap = int(params.get("max_reference_gap", 50000))
        threads = int(params.get("threads", 1))
        timeout = int(params.get("timeout_seconds", 1800))
        binary = str(params.get("minimap2_path", "minimap2"))
        block_dim = str(params.get("block_dim", "block"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "blocks"))

        temporary = Path(tempfile.mkdtemp(prefix="operon_genome_synteny_"))
        try:
            query_path = temporary / "query.fasta"
            reference_path = temporary / "reference.fasta"
            write_fasta(inputs[0], str(params.get("query_sequence_dim", "sequence")),
                        str(params.get("query_position_dim", "position")), query_path, "genome_synteny_blocks")
            write_fasta(inputs[1], str(params.get("reference_sequence_dim", "sequence")),
                        str(params.get("reference_position_dim", "position")), reference_path, "genome_synteny_blocks")
            records = run_minimap2(query_path, reference_path, preset, threads, timeout, binary)
        finally:
            shutil.rmtree(temporary, ignore_errors=True)

        records = [record for record in records
                   if record["block_length"] >= min_block and record["identity"] >= min_identity]
        blocks = chain_blocks(records, min_block, 2000, max_ref_gap)

        labels = []
        data = np.zeros((len(blocks), 8), dtype=np.float64)
        for index, block in enumerate(blocks):
            labels.append(f"block_{index + 1}:{block['reference']}:{block['reference_start']}-{block['reference_end']}")
            data[index, 0] = block["reference_start"]
            data[index, 1] = block["reference_end"]
            data[index, 2] = 1.0 if block["strand"] == "+" else -1.0
            data[index, 3] = block["query_start"]
            data[index, 4] = block["query_end"]
            data[index, 5] = block["n_alignments"]
            data[index, 6] = block["aligned_bp"]
            data[index, 7] = block["identity"]
        field_labels = {
            "ref_start": 0, "ref_end": 1, "strand": 2,
            "query_start": 3, "query_end": 4,
            "n_alignments": 5, "aligned_bp": 6, "identity": 7,
        }
        block_bp = sum(block["aligned_bp"] for block in blocks)
        out = Form(
            data,
            dims=[block_dim, field_dim],
            labels={block_dim: {label: index for index, label in enumerate(labels)},
                    field_dim: field_labels},
            info={
                "n_blocks": len(blocks),
                "block_bp": block_bp,
                "largest_block_bp": max((block["aligned_bp"] for block in blocks), default=0),
                "n_forward_blocks": sum(1 for block in blocks if block["strand"] == "+"),
                "n_reverse_blocks": sum(1 for block in blocks if block["strand"] == "-"),
                "preset": preset,
                "min_block": min_block,
                "n_alignments_used": len(records),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_blocks": len(blocks),
            "block_bp": block_bp,
            "largest_block_bp": max((block["aligned_bp"] for block in blocks), default=0),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))


__all__ = ["GenomeSyntenyBlocksStep"]
