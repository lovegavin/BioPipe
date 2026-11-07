"""Summarise how much of each target chromosome a chain file covers."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

from src.task.step.base import Step
from ._liftover_utils import chain_path, coverage_rows, load_chain

_DEFAULTS = {"chrom": "", "output": "chain_coverage"}

_FIELDS = {
    "n_chains": 0,
    "aligned_bp": 1,
    "covered_bp": 2,
    "coverage_fraction": 3,
    "target_size": 4,
}


class ChainCoverageSummaryStep(Step):
    provider = "operon-core"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "chain_coverage_summary",
        "kind": "operator",
        "title": "Chain coverage summary",
        "description": "Per-chromosome aligned bases and non-redundant chain coverage.",
        "category": "Genome",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "const": "chain"}},
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 1024 * 1024)

    def run(self, ctx, inputs):
        params = dict(_DEFAULTS)
        params.update(ctx.step_params or {})
        operator = self.name or "chain_coverage_summary"
        out_name = str(params.get("output") or self.name or "chain_coverage")

        chains = load_chain(chain_path(inputs[0], operator))
        rows = coverage_rows(chains, params["chrom"] or None)

        data = np.zeros((len(rows), len(_FIELDS)), dtype=float)
        labels = {}
        for index, row in enumerate(rows):
            labels[row["chrom"]] = index
            data[index] = (
                float(row["n_chains"]),
                float(row["aligned_bp"]),
                float(row["covered_bp"]),
                float(row["coverage_fraction"]),
                float(row["t_size"]),
            )
        form = Form(
            data,
            dims=["chrom", "statistic"],
            labels={"chrom": labels, "statistic": dict(_FIELDS)},
            info={
                "source": "chain_coverage_summary",
                "n_chromosomes": len(rows),
                "n_chains": len(chains),
                "total_aligned_bp": int(sum(row["aligned_bp"] for row in rows)),
                "total_covered_bp": int(sum(row["covered_bp"] for row in rows)),
            },
        )
        form.validate()
        ctx[out_name] = form

        self._export_data = {
            "n_chromosomes": len(rows),
            "n_chains": len(chains),
            "total_aligned_bp": int(sum(row["aligned_bp"] for row in rows)),
            "total_covered_bp": int(sum(row["covered_bp"] for row in rows)),
            "top_chromosome": max(rows, key=lambda row: row["covered_bp"])["chrom"],
        }
        print(
            f"[chain_coverage_summary] {len(chains)} chains over {len(rows)} "
            f"chromosomes, {self._export_data['total_covered_bp']} covered bp"
        )

    def export(self, ctx):
        return self._export_data
