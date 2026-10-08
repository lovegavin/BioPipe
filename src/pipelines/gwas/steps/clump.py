# src/pipelines/gwas/steps/clump.py
"""ClumpStep — LD clumping of significant variants."""

from __future__ import annotations

import numpy as np

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step


class ClumpStep(Step):
    """Reduce significant hits to independent signals."""

    name = "clump"
    consumes = ("genotype", "association")
    produces = ()

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["ld"]
        if not cfg.get("clump", False):
            return

        df = ctx.get("association").data
        if "SIGNIFICANT" not in df.columns or not df["SIGNIFICANT"].any():
            print("[clump] no significant variants; skipped")
            return

        genotype = ctx.get("genotype")
        r2_thresh = float(cfg.get("clump_r2", 0.5))
        window_kb = int(cfg.get("clump_window", 500))

        variant_index = {
            v: i for i, v in enumerate(genotype.variant_ids.tolist())
        }
        sig = df[df["SIGNIFICANT"]].sort_values("P")

        keep = self._clump(
            sig,
            genotype.data,
            variant_index,
            genotype.missing_code,
            r2_thresh,
            window_kb,
        )

        indep = sig.loc[keep] if keep else sig.iloc[0:0]

        out = ctx.proc_dir / "independent_significant_snps.tsv"
        indep.to_csv(out, sep="\t", na_rep="NA")
        ctx.artifacts["independent_significant_snps"] = indep
        print(
            f"[clump] {len(sig)} significant -> {len(indep)} independent"
        )

    @staticmethod
    def _clump(
        sig, data, variant_index, missing_code, r2_thresh, window_kb
    ):
        rows = sig.index.tolist()
        chroms = sig["CHROM"].astype(str).tolist()
        positions = sig["POS"].astype(int).tolist()
        removed = np.zeros(len(rows), dtype=bool)
        selected: list[str] = []

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

        for i in range(len(rows)):
            if removed[i]:
                continue
            selected.append(rows[i])
            gi = variant_index.get(rows[i])
            if gi is None:
                continue
            for j in range(i + 1, len(rows)):
                if removed[j]:
                    continue
                if chroms[j] != chroms[i]:
                    continue
                if abs(positions[j] - positions[i]) > window_kb * 1000:
                    continue
                gj = variant_index.get(rows[j])
                if gj is None:
                    continue
                if _r2(data[gi], data[gj]) > r2_thresh:
                    removed[j] = True
        return selected