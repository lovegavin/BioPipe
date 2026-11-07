"""Summarise the consequence classes present in an annotated VCF."""
from __future__ import annotations

from collections import Counter

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps import _vcf_utils as vcf
from src.task.step.steps._variant_utils import CODING_CLASSES, SEVERITY, SPLICE_CLASSES


def _file_path(artifact, operator):
    if not isinstance(artifact, FileArtifact):
        raise StepError(f"{operator} expects a file artifact")
    artifact.validate()
    if str(getattr(artifact, "format", "")) not in {"vcf", "vcf.gz"}:
        raise StepError(f"{operator} expects a VCF artifact")
    return next(iter(artifact.files.values()))


def _info_value(info, key):
    for item in info.split(";"):
        if item.startswith(key + "="):
            return item[len(key) + 1:]
    return ""


class VariantImpactSummaryStep(Step):
    provider = "operon-core"
    parameters_file = "variant_impact_summary.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "variant_impact_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "variant_impact_summary",
        "description": "Count consequence classes and genes in an annotated VCF.",
        "category": "Genome",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "kind": "file", "numeric": False, "ndim": 0, "dims": [],
                 "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}}},
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "version": 1,
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "consequence_dim", "default": "consequence"},
                        {"param": "statistic_dim", "default": "statistic"},
                    ],
                    "labels": {"statistic": ["n_variants", "fraction"]},
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 256 * 1024 * 1024, 4 * 1024 * 1024

    def run(self, ctx: Context, inputs) -> None:
        (annotation,) = inputs
        params = ctx.step_params
        out_name = params.get("output", "summary") or "summary"
        path = _file_path(annotation, "variant_impact_summary")

        counts = Counter()
        genes = Counter()
        total = 0
        with vcf.open_text(path) as stream:
            _meta, _samples, _columns = vcf.read_header(stream)
            for fixed, _rest in vcf.iter_sites(stream):
                total += 1
                consequence = _info_value(fixed[7], "CSQ") or "intergenic"
                counts[consequence] += 1
                gene = _info_value(fixed[7], "GENE")
                if gene:
                    genes[gene] += 1

        classes = [name for name in SEVERITY if counts.get(name)]
        values = []
        for name in classes:
            values.append((float(counts[name]), float(counts[name] / total if total else 0.0)))
        if not classes:
            values.append((0.0, 0.0))
            classes = ["intergenic"]

        data = np.asarray(values, dtype=float)
        form = Form(
            data,
            dims=["consequence", "statistic"],
            labels={
                "consequence": {name: index for index, name in enumerate(classes)},
                "statistic": {"n_variants": 0, "fraction": 1},
            },
            info={
                "total": total,
                "coding_classes": sorted(CODING_CLASSES),
                "splice_classes": sorted(SPLICE_CLASSES),
                "top_genes": genes.most_common(10),
                "n_classes": len(classes),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "total": total,
            "n_classes": len(classes),
            "coding_fraction": float(
                sum(counts[name] for name in CODING_CLASSES) / total if total else 0.0
            ),
            "top_genes": genes.most_common(10),
        }
        print(f"[variant_impact_summary] {total} variants in {len(classes)} classes")

    def export(self, ctx: Context) -> dict:
        return dict(getattr(self, "_export_data", {}))
