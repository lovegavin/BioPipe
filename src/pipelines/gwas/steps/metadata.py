# src/pipelines/gwas/steps/metadata.py
"""MetadataStep — persist run metadata and the primary result table."""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version, PackageNotFoundError

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step

_TRACKED_PACKAGES = (
    "numpy", "pandas", "scipy", "statsmodels",
    "pysam", "bed_reader", "matplotlib",
)


class MetadataStep(Step):
    """Write ``run_metadata.json``, ``gwas_result.tsv`` and side tables."""

    name = "metadata"
    consumes = ("association",)
    produces = ()

    def run(self, ctx: PipelineContext) -> None:
        assoc = ctx.get("association")
        df = assoc.data

        # Primary result table (index materialised as ID column).
        result_path = ctx.out_dir / "gwas_result.tsv"
        df.reset_index().to_csv(result_path, sep="\t", na_rep="NA")

        # Significant subset, if any.
        if "SIGNIFICANT" in df.columns and df["SIGNIFICANT"].any():
            sig = df[df["SIGNIFICANT"]].sort_values("P")
            sig.reset_index().to_csv(
                ctx.proc_dir / "significant_snps.tsv",
                sep="\t", na_rep="NA",
            )

        # Top N table.
        top_n = int(ctx.config["plots"].get("top_n_forest", 20))
        top = df.dropna(subset=["P"]).nsmallest(top_n, "P")
        top.reset_index().to_csv(
            ctx.proc_dir / "top_snps.tsv", sep="\t", na_rep="NA"
        )

        metadata = {
            "pipeline": "gwas",
            "version": ctx.config.get("version", "0.1.0"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "packages": self._package_versions(),
            "config": ctx.config,
            "steps": ctx.metadata.get("steps", []),
            "alignment": ctx.metadata.get("alignment"),
            "sample_qc": ctx.metadata.get("sample_qc"),
            "snp_qc": ctx.metadata.get("snp_qc"),
            "correction": ctx.metadata.get("correction"),
            "input_paths": ctx.metadata.get("input_paths"),
        }

        meta_path = ctx.out_dir / "run_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"[metadata] wrote {meta_path}")
        print(f"[metadata] wrote {result_path}")

    @staticmethod
    def _package_versions() -> dict:
        out = {}
        for name in _TRACKED_PACKAGES:
            try:
                out[name] = pkg_version(name)
            except PackageNotFoundError:
                out[name] = "not installed"
        return out