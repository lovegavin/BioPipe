"""Trim gappy alignment columns and poorly covered rows."""

from __future__ import annotations

import numpy as np

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._msa_utils import alignment_records, trim_alignment
from ._native_results import output_directory, remember_native, result_file


def _wrap(sequence, width=60):
    return [sequence[index:index + width] for index in range(0, len(sequence), width)]


class MsaTrimStep(Step):
    provider = "operon-core"
    parameters_file = "msa_trim.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'file_artifact',
                      'representations': ['file_artifact'],
                      'metadata': {}}]},
        "protocol_version": 3,
        "id": "msa_trim",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Trim alignment columns and rows",
        "description": (
            "Drop alignment columns whose gap fraction exceeds a threshold and "
            "rows that do not cover enough of the retained columns; writes a "
            "trimmed aligned FASTA artifact."
        ),
        "category": "Sequence",
        "icon": "Filter",
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
                "schema": {
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "fasta"}},
                    "info_open": True,
                },
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
        return max(size * 2, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("msa_trim: an alignment input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        max_gap_fraction = float(params.get("max_gap_fraction", 0.5))
        min_row_fraction = float(params.get("min_row_fraction", 0.5))
        out_name = str(params.get("output", self.name))
        if not 0.0 <= max_gap_fraction <= 1.0:
            raise StepError("msa_trim: max_gap_fraction must be within [0, 1]")
        if not 0.0 <= min_row_fraction <= 1.0:
            raise StepError("msa_trim: min_row_fraction must be within [0, 1]")

        names, sequences = alignment_records(
            inputs[0], sequence_dim, position_dim, "msa_trim"
        )
        result = trim_alignment(
            names, sequences, max_gap_fraction, min_row_fraction
        )
        records = []
        for name, sequence in zip(result["names"], result["sequences"]):
            records.append(f">{name}")
            records.extend(_wrap(sequence))
        directory = output_directory(ctx, out_name)
        fasta_out = directory / f"{out_name}.fasta"
        fasta_out.write_bytes(("\n".join(records) + "\n").encode("utf-8"))
        result_files = [
            result_file("alignment", str(fasta_out), "fasta", "Trimmed alignment")
        ]
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = FileArtifact(
            "fasta",
            {"alignment": str(fasta_out)},
            info={"source": "msa_trim"},
        )
        self._result_files = result_files
        self._export_data = {
            "columns_before": result["columns_before"],
            "columns_after": result["columns_after"],
            "columns_removed": result["columns_removed"],
            "rows_before": result["rows_before"],
            "rows_after": result["rows_after"],
            "rows_removed": result["rows_removed"],
            "gap_fraction_before": result["gap_fraction_before"],
            "gap_fraction_after": result["gap_fraction_after"],
            "file": str(fasta_out),
            "bytes": int(fasta_out.stat().st_size),
            "result_files": result_files,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
