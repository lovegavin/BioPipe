# src/pipelines/gwas/steps/sample_qc.py
"""SampleQcStep — remove samples with excessive missingness."""

from __future__ import annotations

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step
from src.qc.missing import filter_by_sample_missing


class SampleQcStep(Step):
    """Filter samples whose missing rate exceeds the configured threshold."""

    name = "sample_qc"
    consumes = ("genotype", "phenotype")
    produces = ("genotype", "phenotype")

    def run(self, ctx: PipelineContext) -> None:
        genotype = ctx.get("genotype")
        phenotype = ctx.get("phenotype")
        covariates = ctx.forms.get("covariates")

        threshold = ctx.config["qc"].get("sample_missing", 0.10)

        genotype, phenotype, covariates, report = filter_by_sample_missing(
            genotype, phenotype, covariates, threshold
        )

        ctx.forms["genotype"] = genotype
        ctx.forms["phenotype"] = phenotype
        if covariates is not None:
            ctx.forms["covariates"] = covariates

        ctx.metadata["sample_qc"] = report