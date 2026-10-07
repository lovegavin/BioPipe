# src/pipelines/gwas/pipeline.py
"""GWAS 主流程编排"""

from pathlib import Path

import pandas as pd
import yaml

from src.datapipe.genotype import read_genotype
from src.datapipe.table import read_table
from src.datapipe.memory import Table
from src.datapipe.align import align
from src.pipelines.gwas.config import validate_config
from src.pipelines.gwas.sample_qc import sample_qc
from src.pipelines.gwas.qc import qc
from src.pipelines.gwas.association import regress
from src.pipelines.gwas.correction import apply_correction
from src.pipelines.gwas.ld import prune_by_ld
from src.pipelines.gwas.clump import clump
from src.pipelines.gwas.pca import compute_pca, append_pcs
from src.pipelines.gwas.plot import plot_all
from src.pipelines.gwas.profile import build_dataset_profile, save_json


def _load_config(task_dir):
    with open(task_dir / "config.yaml") as f:
        return yaml.safe_load(f)


def run(task_dir):
    task_dir = Path(task_dir)
    config = _load_config(task_dir)
    validate_config(config)

    out_dir = task_dir / "output"
    fig_dir = out_dir / "figures"
    proc_dir = task_dir / "processed"
    fig_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    geno_rel = config["input"]["genotype"]
    pheno_rel = config["input"]["phenotype"]
    covar_rel = config["input"].get("covariates")

    geno_path = task_dir / geno_rel
    pheno_path = task_dir / pheno_rel
    covar_path = task_dir / covar_rel if covar_rel else None

    # ---- 1. 读基因型 (返回 GenotypeMatrix) ----
    geno = read_genotype(str(geno_path))

    # ---- 2. 读表型 + 协变量 (返回 Table) ----
    pheno_table = read_table(str(pheno_path), id_col=0)
    # 强制单列, 列名统一为 trait_value
    if pheno_table.data.shape[1] != 1:
        first_col = pheno_table.columns[0]
        pheno_table = Table(
            data=pheno_table.data.iloc[:, [0]].rename(
                columns={first_col: "trait_value"}
            ),
            source_format=pheno_table.source_format,
        )
    else:
        pheno_table.data.columns = ["trait_value"]

    covar_table = None
    if covar_path:
        covar_table = read_table(str(covar_path), id_col=0)

    # ---- 3. 对齐 (dataclass 进, dataclass 出) ----
    n_geno = geno.n_samples
    n_pheno = pheno_table.data.shape[0]
    n_covar = covar_table.data.shape[0] if covar_table is not None else 0

    geno, pheno_table, covar_table = align(geno, pheno_table, covar_table)
    n_common = geno.n_samples

    # ---- 4. 展开为裸数组, 供下游模块使用 ----
    dosage = geno.dosage
    variant_info = geno.variant_info
    sample_ids = geno.sample_ids
    ploidy = geno.ploidy
    phenotype = pheno_table.data          # DataFrame, index=sample_id
    covariates = covar_table.data if covar_table is not None else None

    # ---- 5. 数据快照 ----
    profile = build_dataset_profile(
        geno_rel, pheno_rel, covar_rel,
        dosage, variant_info, sample_ids, ploidy,
        phenotype, covariates,
    )
    profile["alignment"] = {
        "n_common_samples": int(n_common),
        "dropped_from_genotype_only": int(n_geno - n_common),
        "dropped_from_phenotype_only": int(n_pheno - n_common),
        "dropped_from_covariates_only": int(n_covar - n_common),
    }
    save_json(profile, proc_dir / "dataset_profile.json")
    print(f"数据快照: {proc_dir / 'dataset_profile.json'}")

    # ---- 6. 样本 QC ----
    dosage, phenotype, covariates, sample_qc_report = sample_qc(
        dosage, phenotype, covariates,
        missing_thresh=config["qc"].get("sample_missing", 0.10),
    )
    n_common = dosage.shape[1]

    # ---- 7. 可选 LD pruning ----
    pcs = None
    explained_var = None
    if config["ld"]["prune"] or config["pca"]["enabled"]:
        keep = prune_by_ld(
            dosage,
            r2_threshold=config["ld"]["r2"],
            window=config["ld"]["window"],
        )
        dosage_pruned = dosage[keep]
        kept_snps = variant_info["ID"].values[keep]
        (proc_dir / "ld_pruned_snps.txt").write_text(
            "\n".join(map(str, kept_snps)) + "\n", encoding="utf-8"
        )
        print(f"LD 保留 SNP (仅用于 PCA): {proc_dir / 'ld_pruned_snps.txt'}")
    else:
        dosage_pruned = dosage

    # ---- 8. 可选 PCA ----
    if config["pca"]["enabled"]:
        pcs, explained_var = compute_pca(
            dosage_pruned,
            n_components=config["pca"]["n_components"],
        )
        pc_df = pd.DataFrame(
            pcs,
            index=phenotype.index,
            columns=[f"PC{i+1}" for i in range(pcs.shape[1])],
        )
        pc_df.index.name = "sample_id"
        pc_df.to_csv(proc_dir / "pca_result.tsv", sep="\t")

        pd.DataFrame({
            "PC": [f"PC{i+1}" for i in range(explained_var.size)],
            "explained_variance_ratio": explained_var,
        }).to_csv(proc_dir / "pca_variance.tsv", sep="\t", index=False)

        print(f"PCA 结果: {proc_dir / 'pca_result.tsv'}")

        if config["pca"]["as_covariates"]:
            covariates = append_pcs(covariates, pcs)

    # ---- 9. SNP QC ----
    dosage, variant_info, maf, qc_report = qc(
        dosage, variant_info, ploidy, phenotype=phenotype,
        maf_thresh=config["qc"]["maf"],
        missing_thresh=config["qc"]["missing"],
        hwe_thresh=config["qc"].get("hwe", 1e-6),
    )
    qc_report["sample_qc"] = sample_qc_report
    save_json(qc_report, proc_dir / "qc_report.json")
    print(f"QC 报告: {proc_dir / 'qc_report.json'}")

    # ---- 10. 回归 ----
    results = regress(
        dosage, variant_info, maf, phenotype, covariates,
        binary_model=config["association"].get("binary_model", "firth"),
    )

    # ---- 11. 校正 ----
    method = config["correction"].get("method")
    correction_meta = None
    if method:
        results, correction_meta = apply_correction(
            results, method=method,
            fdr_threshold=config["correction"]["fdr_threshold"],
        )
        save_json(correction_meta, proc_dir / "correction_meta.json")

        sig = results[results["SIGNIFICANT"]].sort_values("P")
        sig.to_csv(proc_dir / "significant_snps.tsv", sep="\t",
                   index=False, na_rep="NA")
        print(f"显著 SNP: {proc_dir / 'significant_snps.tsv'} "
              f"({len(sig)} 条)")
    else:
        results["SIGNIFICANT"] = False

    # ---- 12. 主结果 ----
    out_tsv = out_dir / "gwas_result.tsv"
    results.to_csv(out_tsv, sep="\t", index=False, na_rep="NA")
    print(f"结果输出: {out_tsv}")

    # ---- 13. Top SNPs ----
    top_n = int(config["plots"].get("top_n_forest", 20))
    top = results.dropna(subset=["P"]).nsmallest(top_n, "P")
    top.to_csv(proc_dir / "top_snps.tsv", sep="\t",
               index=False, na_rep="NA")

    # ---- 14. LD Clumping ----
    if config["ld"].get("clump", False) and correction_meta is not None:
        indep = clump(
            results, dosage,
            r2_thresh=config["ld"].get("clump_r2", 0.5),
            window_kb=config["ld"].get("clump_window", 500),
        )
        if not indep.empty:
            indep_path = proc_dir / "independent_significant_snps.tsv"
            indep.to_csv(indep_path, sep="\t", index=False, na_rep="NA")
            print(f"独立信号: {indep_path} ({len(indep)} 条)")

    # ---- 15. 绘图 ----
    sig_threshold = None
    if correction_meta and correction_meta.get("threshold"):
        sig_threshold = correction_meta["threshold"]
    plot_all(
        results,
        out_dir=fig_dir,
        config=config,
        sig_threshold=sig_threshold,
        pcs=pcs,
        explained_var=explained_var,
    )

    print("完成")