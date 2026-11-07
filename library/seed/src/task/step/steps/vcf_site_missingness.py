"""Per-site call-rate table for a VCF."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step

from ._vcf_qc_utils import site_missingness, vcf_path

STATISTICS = ("n_called", "n_missing", "call_rate")


class VcfSiteMissingnessStep(Step):
    provider = "operon-core"
    """One row per site with called/missing sample counts and call rate."""

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "version": "1.0.0",
        "id": "vcf_site_missingness",
        "title": "Per-site VCF call rate",
        "category": "Genome",
        "icon": "Table",
        "description": "Per-site called and missing sample counts with the call rate.",
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

    parameters_file = "vcf_site_missingness.parameters.json"

    def run(self, ctx, inputs):
        params = {"max_sites": 0, "output": "site_missingness"}
        params.update(dict(ctx.step_params or {}))
        path = vcf_path(inputs[0], "vcf_site_missingness")
        rows = site_missingness(path, max_sites=int(params["max_sites"]))
        data = np.asarray(
            [[row["n_called"], row["n_missing"], row["call_rate"]] for row in rows], dtype=float
        )
        labels = {row["site"]: index for index, row in enumerate(rows)}
        from src.core import Form

        output_name = str(params.get("output") or "site_missingness")
        ctx[output_name] = Form(
            data,
            dims=["site", "statistic"],
            labels={"site": labels, "statistic": {name: i for i, name in enumerate(STATISTICS)}},
            info={
                "n_sites": len(rows),
                "n_complete": sum(1 for row in rows if row["n_missing"] == 0),
                "statistics": list(STATISTICS),
            },
        )
        return ctx[output_name]

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        form = ctx[name]
        return {"n_sites": int(form.info.get("n_sites", 0))}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return (max(size, 8 * 1024 * 1024), 1024 * 1024)
