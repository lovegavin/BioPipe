# src/pipelines/gwas/steps/load.py
"""LoadStep — read genotype, phenotype and covariate files into forms."""

from __future__ import annotations

from src.io import read
from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class LoadStep(Step):
    """Read every input declared in the manifest into memory forms.

    The ``covariates`` form is optional: it is registered only when the
    manifest declares a covariates path. It is therefore not listed in
    ``produces``; consumers must query ``ctx.forms.get("covariates")``.
    """

    name = "load"
    consumes = ()
    produces = ("genotype", "phenotype")

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["input"]

        geno_path = str(ctx.task_dir / cfg["genotype"])
        pheno_path = str(ctx.task_dir / cfg["phenotype"])
        covar_rel = cfg.get("covariates")
        covar_path = str(ctx.task_dir / covar_rel) if covar_rel else None

        geno_forms = read(geno_path, role="genotype")
        ctx.put("genotype", geno_forms["genotype"])
        ctx.put("variant_table", geno_forms["variant_table"])
        ctx.put("sample_table", geno_forms["sample_table"])

        pheno_forms = read(pheno_path, role="phenotype")
        ctx.put("phenotype", pheno_forms["phenotype"])

        if covar_path:
            cov_forms = read(covar_path, role="covariates")
            ctx.put("covariates", cov_forms["covariates"])
        else:
            ctx.artifacts["covariates_absent"] = True

        ctx.metadata["input_paths"] = {
            "genotype": cfg["genotype"],
            "phenotype": cfg["phenotype"],
            "covariates": covar_rel,
        }