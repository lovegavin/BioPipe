# src/pipelines/gwas/steps/correction.py
"""CorrectionStep — multiple-testing correction and lambda-GC."""

from __future__ import annotations

import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests

from src.core.forms import ResultTable
from src.orchestration.context import PipelineContext
from src.orchestration.step import Step

CHI2_MEDIAN = 0.4549364


class CorrectionStep(Step):
    """Apply Bonferroni or FDR correction; compute lambda-GC."""

    name = "correction"
    consumes = ("association",)
    produces = ("association",)

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["correction"]
        method = cfg.get("method")

        assoc = ctx.get("association")
        df = assoc.data.copy()

        pvals = df["P"].to_numpy()
        valid = np.isfinite(pvals)
        n_tests = int(valid.sum())

        lambda_gc = self._lambda_gc(pvals)
        meta = {
            "method": method,
            "n_tests": n_tests,
            "lambda_gc": lambda_gc,
        }

        if method is None:
            df["SIGNIFICANT"] = False
            meta["threshold"] = None
            meta["n_significant"] = 0
        elif method == "bonferroni":
            threshold = 0.05 / max(n_tests, 1)
            df["SIGNIFICANT"] = valid & (pvals < threshold)
            meta["threshold"] = float(threshold)
            meta["n_significant"] = int(df["SIGNIFICANT"].sum())
        elif method == "fdr":
            q = np.full(len(pvals), np.nan)
            if n_tests > 0:
                _, q_valid, _, _ = multipletests(
                    pvals[valid], method="fdr_bh"
                )
                q[valid] = q_valid
            df["Q_VALUE"] = q
            df["SIGNIFICANT"] = q < cfg.get("fdr_threshold", 0.05)
            meta["threshold"] = float(cfg.get("fdr_threshold", 0.05))
            meta["n_significant"] = int(df["SIGNIFICANT"].sum())
        else:
            raise ValueError(f"Unknown correction method: {method}")

        ctx.put(
            "association",
            ResultTable(
                data=df,
                id_column=assoc.id_column,
                id_kind=assoc.id_kind,
                source_format=assoc.source_format,
            ),
        )
        ctx.metadata["correction"] = meta

        print(
            f"[correction] method={method} "
            f"lambda_gc={lambda_gc:.3f} "
            f"significant={meta['n_significant']}"
        )

    @staticmethod
    def _lambda_gc(pvals: np.ndarray) -> float:
        p = pvals[np.isfinite(pvals) & (pvals > 0) & (pvals <= 1)]
        if p.size == 0:
            return float("nan")
        chi2 = stats.chi2.isf(p, df=1)
        return float(np.median(chi2) / CHI2_MEDIAN)