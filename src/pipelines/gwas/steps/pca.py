# src/pipelines/gwas/steps/pca.py
"""PcaStep — compute principal components and append them to covariates."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core.forms import Table
from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class PcaStep(Step):
    """Compute PCs on the LD-pruned matrix and optionally use them as covariates."""

    name = "pca"
    consumes = ("genotype",)
    produces = ()

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["pca"]
        if not cfg.get("enabled", True):
            ctx.artifacts["pca_disabled"] = True
            return

        genotype = ctx.get("genotype")
        mask = ctx.artifacts["ld_pruned_mask"]
        data = genotype.data[mask]

        n_components = int(cfg.get("n_components", 10))
        pcs, explained = self._compute_pca(
            data, genotype.missing_code, n_components
        )

        sample_ids = genotype.sample_ids.tolist()
        pc_df = pd.DataFrame(
            pcs,
            index=pd.Index(sample_ids, name="sample_id"),
            columns=[f"PC{i+1}" for i in range(pcs.shape[1])],
        )
        pc_df.to_csv(ctx.proc_dir / "pca_result.tsv", sep="\t")

        pd.DataFrame({
            "PC": [f"PC{i+1}" for i in range(explained.size)],
            "explained_variance_ratio": explained,
        }).to_csv(ctx.proc_dir / "pca_variance.tsv", sep="\t", index=False)

        ctx.artifacts["pcs"] = pcs
        ctx.artifacts["explained_var"] = explained

        if cfg.get("as_covariates", True):
            cov = ctx.forms.get("covariates")
            if cov is None:
                new_cov = Table(
                    data=pc_df, index_name="sample_id",
                    source_format="derived",
                )
            else:
                merged = cov.data.join(pc_df, how="left")
                new_cov = Table(
                    data=merged, index_name=cov.index_name,
                    source_format="derived",
                )
            ctx.put("covariates", new_cov)

        print(
            f"[pca] {pcs.shape[1]} components, "
            f"PC1={explained[0]*100:.2f}%, PC2={explained[1]*100:.2f}%"
        )

    @staticmethod
    def _compute_pca(
        data: np.ndarray,
        missing_code: float,
        n_components: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        X = data.T.astype(np.float64)  # samples x variants

        mask = X == missing_code
        if mask.any():
            col_mean = np.nanmean(np.where(mask, np.nan, X), axis=0)
            col_mean = np.nan_to_num(col_mean, nan=0.0)
            idx = np.where(mask)
            X[idx] = np.take(col_mean, idx[1])

        mean = X.mean(axis=0, keepdims=True)
        std = X.std(axis=0, keepdims=True)
        std[std < 1e-8] = 1.0
        X = (X - mean) / std

        U, S, _ = np.linalg.svd(X, full_matrices=False)
        k = min(n_components, S.size)
        pcs = U[:, :k] * S[:k]
        var = S ** 2
        explained = var[:k] / var.sum()
        return pcs, explained