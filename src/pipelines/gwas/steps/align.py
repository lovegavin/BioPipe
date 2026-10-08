# src/pipelines/gwas/steps/align.py
"""AlignStep — form-agnostic sample alignment."""

from __future__ import annotations

from src.align import align_forms
from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class AlignStep(Step):
    """Align all sample-indexed forms in the context.

    The step delegates entirely to :func:`align_forms`. It does not
    know which forms are present beyond the fact that they are
    sample-indexed. The phenotype form defines the reference order.
    """

    name = "align"
    consumes = ("genotype", "phenotype")
    produces = ("genotype", "phenotype")

    def run(self, ctx: PipelineContext) -> None:
        # Collect every sample-indexed form currently in the context.
        # Non-sample forms (e.g. variant_table) are intentionally
        # excluded; align_forms would ignore them anyway.
        candidates = {
            name: ctx.forms[name]
            for name in ("genotype", "phenotype", "covariates", "sample_table")
            if name in ctx.forms
        }

        aligned, report = align_forms(candidates, reference="phenotype")

        for name, form in aligned.items():
            ctx.forms[name] = form

        ctx.metadata["alignment"] = report