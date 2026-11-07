"""Per-sample call, genotype and transition/transversion statistics for a VCF."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError

from src.task.step.base import Step

from ._vcf_qc_utils import sample_summary, vcf_path

STATISTICS = (
    "n_called",
    "n_missing",
    "call_rate",
    "n_het",
    "n_hom_ref",
    "n_hom_alt",
    "het_hom_ratio",
    "ti_tv",
)


class VcfSampleStatsStep(Step):
    provider = "operon-core"
    """One row per sample with call-rate, heterozygosity and Ti/Tv ratios."""

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "version": "1.0.0",
        "id": "vcf_sample_stats",
        "title": "Per-sample VCF genotype statistics",
        "category": "Genome",
        "icon": "Users",
        "description": "Per-sample call rate, genotype counts, heterozygosity ratio and Ti/Tv.",
        "protocol_version": 3,
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "genotypes",
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "labels": [],
                    "parallel": [],
                    "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "external_tools": []},
    }

    parameters_file = "vcf_sample_stats.parameters.json"

    def run(self, ctx, inputs):
        params = {"max_sites": 0, "output": "sample_stats"}
        params.update(dict(ctx.step_params or {}))
        path = vcf_path(inputs[0], "vcf_sample_stats")
        max_sites = int(params["max_sites"])
        result = sample_summary(path, max_sites=max_sites)
        samples = list(result["samples"])
        rows = []
        sample_labels = {}
        for index, name in enumerate(samples):
            entry = result["samples"][name]
            called = entry["called"]
            missing = entry["missing"]
            het = entry["het"]
            hom = entry["hom_ref"] + entry["hom_alt"]
            ts = entry["ts"]
            tv = entry["tv"]
            rows.append(
                [
                    called,
                    missing,
                    called / (called + missing) if called + missing else 0.0,
                    het,
                    entry["hom_ref"],
                    entry["hom_alt"],
                    het / hom if hom else 0.0,
                    ts / tv if tv else 0.0,
                ]
            )
            sample_labels[name] = index
        data = np.asarray(rows, dtype=float)
        output_name = str(params.get("output") or "sample_stats")
        ctx[output_name] = self._form(data, sample_labels, result)
        return ctx[output_name]

    def _form(self, data, sample_labels, result):
        from src.core import Form

        return Form(
            data,
            dims=["sample", "statistic"],
            labels={
                "sample": sample_labels,
                "statistic": {name: i for i, name in enumerate(STATISTICS)},
            },
            info={
                "n_samples": result["n_samples"],
                "n_sites": result["n_sites"],
                "mode": "per-sample",
                "statistics": list(STATISTICS),
            },
        )

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        form = ctx[name]
        return {
            "n_samples": int(form.info.get("n_samples", 0)),
            "n_sites": int(form.info.get("n_sites", 0)),
            "statistics": list(form.labels.get("statistic", {})),
        }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return (max(size, 8 * 1024 * 1024), 1024 * 1024)
