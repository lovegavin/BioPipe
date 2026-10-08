# src/pipelines/gwas/steps/ld_prune.py
"""LdPruneStep — sliding-window LD pruning for PCA input.

Pruning is used only for PCA. Association testing still operates on
the full QC-passed variant set, matching PLINK / REGENIE / SAIGE.
"""

from __future__ import annotations

import numpy as np

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class LdPruneStep(Step):
    """Compute an LD-pruned variant subset and store it as an artefact."""

    name = "ld_prune"
    consumes = ("genotype",)
    produces = ()

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["ld"]
        pca_cfg = ctx.config["pca"]
        need_prune = cfg.get("prune", True) or pca_cfg.get("enabled", True)

        genotype = ctx.get("genotype")

        if not need_prune:
            ctx.artifacts["ld_pruned_mask"] = np.ones(
                genotype.n_snps, dtype=bool
            )
            return

        r2_threshold = float(cfg.get("r2", 0.2))
        window = int(cfg.get("window", 100))

        mask = self._prune(
            genotype.data, genotype.missing_code, r2_threshold, window
        )
        ctx.artifacts["ld_pruned_mask"] = mask

        # Persist the pruned variant IDs for inspection.
        pruned_ids = genotype.variant_ids[mask]
        out = ctx.proc_dir / "ld_pruned_snps.txt"
        out.write_text("\n".join(map(str, pruned_ids)) + "\n", encoding="utf-8")
        ctx.artifacts["ld_pruned_snps_path"] = str(out)

        print(
            f"[ld_prune] {genotype.n_snps} -> {int(mask.sum())} variants "
            f"(r2>{r2_threshold}, window={window})"
        )

    @staticmethod
    def _prune(
        data: np.ndarray,
        missing_code: float,
        r2_threshold: float,
        window: int,
    ) -> np.ndarray:
        n_snps = data.shape[0]
        keep = np.ones(n_snps, dtype=bool)

        def _r2(x, y):
            valid = (x != missing_code) & (y != missing_code)
            if valid.sum() < 3:
                return 0.0
            xv = x[valid].astype(float)
            yv = y[valid].astype(float)
            if xv.std() < 1e-8 or yv.std() < 1e-8:
                return 0.0
            r = np.corrcoef(xv, yv)[0, 1]
            return 0.0 if not np.isfinite(r) else float(r * r)

        for i in range(n_snps):
            if not keep[i]:
                continue
            upper = min(i + window + 1, n_snps)
            for j in range(i + 1, upper):
                if not keep[j]:
                    continue
                if _r2(data[i], data[j]) > r2_threshold:
                    keep[j] = False
        return keep