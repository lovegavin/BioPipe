# src/pipelines/gwas/pipeline.py
"""GwasPipeline — the plugin entry point for the GWAS workflow."""

from __future__ import annotations

from pathlib import Path

from src.orchestration.bootstrap import bootstrap_context, load_manifest
from src.orchestration.runner import run_pipeline
from src.orchestration.step import Step
from src.pipelines.gwas.manifest import validate_manifest
from src.pipelines.gwas.steps import (
    AlignStep,
    AssocStep,
    ClumpStep,
    CorrectionStep,
    LdPruneStep,
    LoadStep,
    MetadataStep,
    PcaStep,
    PlotStep,
    SampleQcStep,
    SnpQcStep,
)
from src.version import __version__


class GwasPipeline:
    """Genome-wide association study pipeline.

    Step order rationale
    --------------------
    Variant QC (``snp_qc``) precedes LD pruning and PCA so that both
    operate on the filtered matrix: monomorphic and low-quality
    variants would otherwise distort the correlation structure and the
    principal components. Association testing uses the same filtered
    matrix.
    """

    name = "gwas"
    version = __version__
    consumes = ("genotype", "phenotype")
    produces = ("association",)

    steps: list[Step] = [
        LoadStep(),
        AlignStep(),
        SampleQcStep(),
        SnpQcStep(),
        LdPruneStep(),
        PcaStep(),
        AssocStep(),
        CorrectionStep(),
        ClumpStep(),
        PlotStep(),
        MetadataStep(),
    ]

    def run(self, task_dir: Path) -> None:
        """Execute the pipeline against a task directory.

        Directory layout, logging and context construction are handled
        by :func:`bootstrap_context`. This method is responsible only
        for loading and validating the manifest, then handing off to
        the runner.
        """
        task_dir = Path(task_dir)
        config = load_manifest(task_dir)
        validate_manifest(config)
        ctx = bootstrap_context(task_dir, config, self.name)
        run_pipeline(self.steps, ctx)