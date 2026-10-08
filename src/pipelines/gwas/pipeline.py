# src/pipelines/gwas/pipeline.py
"""GwasPipeline — the plugin entry point for the GWAS workflow."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from src.orchestration.context import PipelineContext
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


class GwasPipeline:
    """Genome-wide association study pipeline."""

    name = "gwas"
    version = "0.1.0"
    consumes = ("genotype", "phenotype")
    produces = ("association",)

    steps: list[Step] = [
        LoadStep(),
        AlignStep(),
        SampleQcStep(),
        LdPruneStep(),
        PcaStep(),
        SnpQcStep(),
        AssocStep(),
        CorrectionStep(),
        ClumpStep(),
        PlotStep(),
        MetadataStep(),
    ]

    def run(self, task_dir: Path) -> None:
        """Execute the pipeline against a task directory."""
        task_dir = Path(task_dir)

        config = self._load_manifest(task_dir)
        validate_manifest(config)

        out_dir = task_dir / "output"
        proc_dir = task_dir / "processed"
        fig_dir = out_dir / "figures"
        log_dir = task_dir / "logs"

        for d in (out_dir, proc_dir, fig_dir, log_dir):
            d.mkdir(parents=True, exist_ok=True)

        logger = self._build_logger(log_dir)

        seed = int(config.get("runtime", {}).get("seed", 42))
        device = config.get("runtime", {}).get("device", "cpu")

        ctx = PipelineContext(
            config=config,
            task_dir=task_dir,
            out_dir=out_dir,
            proc_dir=proc_dir,
            fig_dir=fig_dir,
            log_dir=log_dir,
            logger=logger,
            rng=np.random.default_rng(seed),
            device=device,
        )
        ctx.metadata["seed"] = seed

        run_pipeline(self.steps, ctx)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_manifest(task_dir: Path) -> dict:
        import yaml

        path = task_dir / "manifest.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing manifest: {path}\n"
                f"Run scripts/init_task.py first."
            )
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    @staticmethod
    def _build_logger(log_dir: Path) -> logging.Logger:
        logger = logging.getLogger("biopipe.gwas")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )

        fh = logging.FileHandler(log_dir / "run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        return logger