"""Per-column statistics for a multiple sequence alignment."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._msa_utils import alignment_records, column_statistics, resolve_alphabet


class MsaColumnStatsStep(Step):
    provider = "operon-core"
    parameters_file = "msa_column_stats.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "msa_column_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Alignment column statistics",
        "description": (
            "Compute per-column gap fraction, Shannon entropy (bits), "
            "conservation (1 - H/log2 alphabet) and majority residue fraction "
            "for a multiple sequence alignment."
        ),
        "category": "Sequence",
        "icon": "ChartBar",
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
        return max(size * 2, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("msa_column_stats: an alignment input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        column_dim = str(params.get("column_dim", "column"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", self.name))

        names, sequences = alignment_records(
            inputs[0], sequence_dim, position_dim, "msa_column_stats"
        )
        alphabet = resolve_alphabet(sequences, params.get("alphabet", "auto"))
        stats = column_statistics(sequences, alphabet)
        n_columns = len(sequences[0])
        columns = ["gap_fraction", "entropy", "conservation", "major_fraction"]
        matrix = np.column_stack(
            [stats["gap_fraction"], stats["entropy"], stats["conservation"], stats["major_fraction"]]
        ).astype(np.float64)
        form = Form(
            matrix,
            dims=[column_dim, statistic_dim],
            labels={
                column_dim: {str(index): index for index in range(n_columns)},
                statistic_dim: {name: index for index, name in enumerate(columns)},
            },
            info={
                "n_sequences": len(sequences),
                "n_columns": n_columns,
                "alphabet": alphabet,
                "consensus": "".join(stats["consensus"]),
                "mean_gap_fraction": float(stats["gap_fraction"].mean()),
                "mean_entropy": float(stats["entropy"].mean()),
                "conserved_columns": int(
                    np.count_nonzero(
                        (stats["entropy"] == 0.0) & (stats["gap_fraction"] == 0.0)
                    )
                ),
                "variable_columns": int(np.count_nonzero(stats["entropy"] > 0.0)),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n_sequences": len(sequences),
            "n_columns": n_columns,
            "alphabet": alphabet,
            "mean_gap_fraction": float(stats["gap_fraction"].mean()),
            "mean_entropy": float(stats["entropy"].mean()),
            "conserved_columns": form.info["conserved_columns"],
            "variable_columns": form.info["variable_columns"],
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
