"""Summarise a Hi-C pairs file: cis/trans balance and per-chromosome counts."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.step.base import Step

from . import _hic_utils as hic

_ROWS = ["total_pairs", "cis_pairs", "trans_pairs", "cis_fraction", "chromosomes", "mean_cis_distance"]


def _file_path(artifact, operator):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    return next(iter(artifact.files.values()))


class HicPairStatsStep(Step):
    provider = "operon-core"
    parameters_file = "hic_pair_stats.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "hic_pair_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "hic_pair_stats",
        "description": "Count cis and trans contacts in a Hi-C pairs file.",
        "category": "Genome",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["pairs", "pairs.gz"]}}},
            ],
            "output": {"mode": "declare", "schema": {
                "kind": "form", "numeric": True, "ndim": 2,
                "dims": [{"param": "statistic_dim", "default": "statistic"}, {"param": "value_dim", "default": "value"}],
                "labels": {"statistic": ["total_pairs", "cis_pairs", "trans_pairs", "cis_fraction", "chromosomes", "mean_cis_distance"],
                             "value": ["value"]},
                "info_open": True,
            }},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = 0
        for item in inputs or []:
            try:
                size += int(item.get("size_bytes") or 0)
            except AttributeError:
                pass
        return max(size, 32 * 1024 * 1024), 0

    def run(self, ctx, input_forms):
        out_name = ctx.step_params.get("output", "stats")
        path = _file_path(input_forms[0], "hic_pair_stats")
        stats = hic.pair_statistics(path, int(ctx.step_params.get("max_pairs", 0)))
        values = [float(stats["total"]), float(stats["cis"]), float(stats["trans"]),
                  float(stats["cis_fraction"]), float(stats["chromosomes"]),
                  float(stats["mean_cis_distance"])]
        data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
        info = {
            "statistic_dim": "statistic",
            "value_dim": "value",
            "n_pairs": stats["total"],
            "per_chromosome": dict(stats["per_chrom"]),
        }
        form = Form(data, dims=["statistic", "value"],
                    labels={"statistic": {name: index for index, name in enumerate(_ROWS)},
                            "value": {"value": 0}},
                    info=info)
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "total_pairs": stats["total"], "cis_pairs": stats["cis"], "trans_pairs": stats["trans"],
            "cis_fraction": stats["cis_fraction"], "chromosomes": stats["chromosomes"],
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
