# src/pipelines/gwas/steps/snp_qc.py
"""SnpQcStep — missingness, MAF and HWE filtering."""

from __future__ import annotations

import numpy as np

from src.orchestration.context import PipelineContext
from src.orchestration.step import Step
from src.qc.hwe import compute_hwe_pvalues
from src.qc.maf import compute_maf
from src.qc.missing import compute_missing_rate


class SnpQcStep(Step):
    """Filter variants by missingness, MAF and HWE."""

    name = "snp_qc"
    consumes = ("genotype", "phenotype")
    produces = ("genotype",)

    def run(self, ctx: PipelineContext) -> None:
        cfg = ctx.config["qc"]
        genotype = ctx.get("genotype")
        phenotype = ctx.get("phenotype")

        missing_thresh = float(cfg.get("missing", 0.10))
        maf_thresh = float(cfg.get("maf", 0.01))
        hwe_thresh = cfg.get("hwe", 1e-6)

        data = genotype.data
        missing_code = genotype.missing_code
        ploidy = genotype.ploidy

        missing = compute_missing_rate(data, missing_code, axis=1)
        maf = compute_maf(data, ploidy, missing_code)

        keep = (missing <= missing_thresh) & (maf >= maf_thresh)
        n_removed_missing = int((missing > missing_thresh).sum())
        n_removed_maf = int(
            ((missing <= missing_thresh) & (maf < maf_thresh)).sum()
        )

        # HWE applies only to diploid data with a threshold.
        hwe_info = {"applied": False}
        if ploidy == 2 and hwe_thresh is not None:
            y = phenotype.data.iloc[:, 0].to_numpy()
            hwe_pvals, scope = compute_hwe_pvalues(
                data, y, missing_code
            )
            with np.errstate(invalid="ignore"):
                hwe_fail = (~np.isnan(hwe_pvals)) & (hwe_pvals < hwe_thresh)
            n_removed_hwe = int((keep & hwe_fail).sum())
            keep &= ~hwe_fail
            hwe_info = {
                "applied": True,
                "threshold": float(hwe_thresh),
                "scope": scope,
                "n_removed": n_removed_hwe,
            }
        elif ploidy > 2:
            hwe_info = {"applied": False, "skipped_reason": "polyploid"}
        else:
            hwe_info = {"applied": False, "skipped_reason": "disabled"}

        genotype_f = genotype.subset_snps(keep)
        ctx.put("genotype", genotype_f)
        ctx.artifacts["maf"] = maf[keep]

        report = {
            "ploidy": int(ploidy),
            "maf_threshold": float(maf_thresh),
            "missing_threshold": float(missing_thresh),
            "n_snps_before": int(genotype.n_snps),
            "n_snps_after": int(genotype_f.n_snps),
            "n_removed_missing": n_removed_missing,
            "n_removed_maf": n_removed_maf,
            "hwe": hwe_info,
        }
        ctx.metadata["snp_qc"] = report

        print(
            f"[snp_qc] {genotype.n_snps} -> {genotype_f.n_snps} variants "
            f"(missing={n_removed_missing}, maf={n_removed_maf})"
        )