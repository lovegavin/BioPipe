# src/pipelines/gwas/steps/plot.py
"""PlotStep — produce the standard GWAS figure set."""

from __future__ import annotations

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step
from src.pipelines.gwas.plot import plot_all


class PlotStep(Step):
    """Render all figures declared in the manifest."""

    name = "plot"
    consumes = ("association",)
    produces = ()

    def run(self, ctx: PipelineContext) -> None:
        assoc = ctx.get("association")

        # Plot helpers expect ID/CHROM/POS as columns, not index.
        df = assoc.data.reset_index()

        sig_threshold = None
        correction_meta = ctx.metadata.get("correction")
        if correction_meta and correction_meta.get("threshold"):
            sig_threshold = correction_meta["threshold"]

        plot_all(
            df,
            out_dir=ctx.fig_dir,
            config=ctx.config,
            sig_threshold=sig_threshold,
            pcs=ctx.artifacts.get("pcs"),
            explained_var=ctx.artifacts.get("explained_var"),
        )