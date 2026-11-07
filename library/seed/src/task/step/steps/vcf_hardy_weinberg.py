"""Hardy-Weinberg exact test and observed/expected heterozygosity per site."""
from __future__ import annotations

import numpy as np

from src.task.step.base import Step

from ._vcf_qc_utils import hwe_rows, vcf_path

STATISTICS = ("n_called", "obs_het", "exp_het", "alt_freq", "hwe_p")


class VcfHardyWeinbergStep(Step):
    provider = "operon-core"
    """Wigginton exact HWE test plus observed/expected heterozygote counts."""

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "version": "1.0.0",
        "id": "vcf_hardy_weinberg",
        "title": "Hardy-Weinberg exact test",
        "category": "Genome",
        "icon": "Scale",
        "description": "Per-site exact Hardy-Weinberg test with observed and expected heterozygotes.",
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

    parameters_file = "vcf_hardy_weinberg.parameters.json"

    def run(self, ctx, inputs):
        params = {"max_sites": 0, "output": "hwe"}
        params.update(dict(ctx.step_params or {}))
        path = vcf_path(inputs[0], "vcf_hardy_weinberg")
        rows = hwe_rows(path, max_sites=int(params["max_sites"]))
        data = np.asarray(
            [
                [row["n_called"], row["obs_het"], row["exp_het"], row["alt_freq"], row["hwe_p"]]
                for row in rows
            ],
            dtype=float,
        )
        labels = {row["site"]: index for index, row in enumerate(rows)}
        from src.core import Form

        output_name = str(params.get("output") or "hwe")
        ctx[output_name] = Form(
            data,
            dims=["site", "statistic"],
            labels={"site": labels, "statistic": {name: i for i, name in enumerate(STATISTICS)}},
            info={
                "n_sites": len(rows),
                "n_below_1e_3": sum(1 for row in rows if row["hwe_p"] < 1e-3),
                "statistics": list(STATISTICS),
            },
        )
        return ctx[output_name]

    def export(self, ctx):
        name = (ctx.step_params or {}).get("output") or self.name
        form = ctx[name]
        return {
            "n_sites": int(form.info.get("n_sites", 0)),
            "n_below_1e_3": int(form.info.get("n_below_1e_3", 0)),
        }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs)
        return (max(size, 8 * 1024 * 1024), 1024 * 1024)
