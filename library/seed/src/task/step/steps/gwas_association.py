"""Genome-wide association testing for biallelic SNPs."""

from __future__ import annotations

import numpy as np

from src.core import FileArtifact, Form, StepError
from src.task.step.base import Step

from ._gwas_utils import align, association, phenotype_from_form, read_vcf


DEFAULTS = {'model': 'linear', 'min_maf': 0.0, 'max_variants': 0, 'row_dim': 'sample', 'field_dim': 'field', 'value_field': 'value', 'output': 'association'}


class GwasAssociationStep(Step):
    parameters_file = "gwas_association.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "gwas_association",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GWAS association testing",
        "description": "Fit a per-variant additive linear or logistic model and report effect size, standard error and p-value.",
        "category": "Statistics",
        "icon": "Activity",
        "inputs_arity": 2,
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
                    "info": {"representation": {"type": "string", "enum": ["vcf", "vcf.gz"]}},
                    "description": "Biallelic SNP genotypes in VCF format.",
                },
                {
                    "version": 1,
                    "name": "phenotype",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "row_dim", "default": "sample"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "description": "Sample-indexed phenotype table.",
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
    }

    parameters = [
        {"name": "model", "type": "string", "default": "linear", "choices": ["linear", "logistic"]},
        {"name": "min_maf", "type": "number", "default": 0.0, "minimum": 0.0, "maximum": 0.5},
        {"name": "max_variants", "type": "integer", "default": 0, "minimum": 0},
        {"name": "row_dim", "type": "string", "default": "sample"},
        {"name": "field_dim", "type": "string", "default": "field"},
        {"name": "value_field", "type": "string", "default": "value"},
        {"name": "output", "type": "string", "default": "association"},
    ]

    def run(self, ctx, inputs):
        params = {**DEFAULTS, **dict(ctx.step_params or {})}
        genotype = inputs[0]
        if not isinstance(genotype, FileArtifact) or genotype.format not in {"vcf", "vcf.gz"}:
            raise StepError("gwas_association: first input must be a VCF file artifact")
        genotype.validate()
        path = next(iter(genotype.files.values()))
        table = phenotype_from_form(
            inputs[1],
            params["row_dim"],
            params["field_dim"],
            params["value_field"],
            "gwas_association",
        )
        samples, variants, dosages = read_vcf(path, int(params["max_variants"]))
        values = align(samples, table, "gwas_association")
        rows = association(
            samples,
            variants,
            dosages,
            dict(zip(samples, values.tolist())),
            model=params["model"],
            min_maf=float(params["min_maf"]),
        )
        if not rows:
            raise StepError("gwas_association: no variant passed the filters")
        statistics = ("beta", "se", "stat", "p", "maf", "n")
        names = {
            f"{row['chrom']}:{row['pos']}:{row['ref']}:{row['alt']}": index
            for index, row in enumerate(rows)
        }
        data = np.asarray([[row[key] for key in statistics] for row in rows], dtype=float)
        labels = {
            "variant": names,
            "statistic": {name: index for index, name in enumerate(statistics)},
        }
        info = {
            "model": params["model"],
            "n_variants": len(rows),
            "min_maf": float(params["min_maf"]),
        }
        ctx[params["output"]] = Form(
            data, dims=["variant", "statistic"], labels=labels, info=info
        )
        self._export = {
            "n_variants": len(rows),
            "n_tested": len(rows),
            "model": params["model"],
        }

    def export(self, ctx):
        return dict(self._export)
