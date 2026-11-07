"""Harmonise PGS Catalog weights against VCF REF/ALT alleles."""
from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _prs_utils as prs_utils


def _file_path(artifact, operator, formats):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    fmt = str(getattr(artifact, "format", ""))
    if formats and fmt not in formats:
        raise StepError(f"{operator} expects format {'/'.join(sorted(formats))}, got {fmt!r}")
    return next(iter(artifact.files.values()))


class PrsHarmonizeStep(Step):
    provider = "operon-core"
    parameters_file = "prs_harmonize.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "prs_harmonize",
        "version": "1.0.0",
        "kind": "operator",
        "title": "prs_harmonize",
        "description": "Match score-file weights to VCF variants and orient them to the ALT allele.",
        "category": "Omics",
        "icon": "GitCompare",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}}},
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["tsv", "txt", "tsv.gz", "txt.gz"]}}},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "version": 1,
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "variant_dim", "default": "variant"},
                        {"param": "statistic_dim", "default": "statistic"},
                    ],
                    "info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 256 * 1024 * 1024, 8 * 1024 * 1024

    def run(self, ctx: Context, inputs) -> None:
        genotypes, weights_artifact = inputs
        params = ctx.step_params
        variant_dim = params.get("variant_dim", "variant") or "variant"
        stat_dim = params.get("statistic_dim", "statistic") or "statistic"
        out_name = params.get("output", "harmonized") or "harmonized"

        vcf_path = _file_path(genotypes, "prs_harmonize", {"vcf", "vcf.gz"})
        weights_path = _file_path(weights_artifact, "prs_harmonize", {"tsv", "txt", "tsv.gz", "txt.gz"})

        _, records = prs_utils.vcf_variants(vcf_path)
        weights = prs_utils.read_pgs_weights(weights_path)
        entries, counts, duplicated = prs_utils.harmonize(records, weights)
        if not entries:
            raise StepError("prs_harmonize: no weight could be oriented to a VCF ALT allele")

        entries.sort(key=lambda item: item["label"])
        names = [item["label"] for item in entries]
        data = np.asarray([[item["weight"]] for item in entries], dtype=float)
        form = Form(
            data,
            dims=[variant_dim, stat_dim],
            labels={variant_dim: {name: index for index, name in enumerate(names)},
                    stat_dim: {"weight": 0}},
            info={
                "n_weights": len(weights),
                "n_variants": len(entries),
                "n_matched": counts["matched"],
                "n_flipped": counts["flipped"],
                "n_ambiguous": counts["ambiguous"],
                "n_absent": counts["absent"],
                "n_multiallelic": counts["multiallelic"],
                "n_duplicate_labels": duplicated,
                "effect_allele": "ALT",
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "n_weights": len(weights),
            "n_variants": len(entries),
            "matched": counts["matched"],
            "flipped": counts["flipped"],
            "ambiguous": counts["ambiguous"],
            "absent": counts["absent"],
            "multiallelic": counts["multiallelic"],
        }

    def export(self, ctx):
        data = getattr(self, "_export_data", {})
        return {
            "n_weights": data.get("n_weights", 0),
            "n_variants": data.get("n_variants", 0),
            "matched": data.get("matched", 0),
            "flipped": data.get("flipped", 0),
            "ambiguous": data.get("ambiguous", 0),
            "absent": data.get("absent", 0),
            "multiallelic": data.get("multiallelic", 0),
        }
