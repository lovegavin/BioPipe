# src/datapipe/align.py
"""样本对齐：以 pheno 顺序为基准，取交集，重排三者。"""

from src.datapipe.memory import GenotypeMatrix, Table


def align(geno: GenotypeMatrix, pheno: Table, covariates: Table = None):
    """
    返回对齐后的 (geno, pheno, covariates)，三者样本顺序一致。
    """
    pheno_ids = list(pheno.index)
    id2col = {s: i for i, s in enumerate(geno.sample_ids)}

    common = [s for s in pheno_ids if s in id2col]

    if covariates is not None:
        cov_ids = set(covariates.index)
        common = [s for s in common if s in cov_ids]

    if not common:
        raise ValueError("基因型与表型无交集样本")

    col_idx = [id2col[s] for s in common]

    geno = geno.subset_samples(col_idx)
    pheno = pheno.subset_rows(common)
    if covariates is not None:
        covariates = covariates.subset_rows(common)

    print(f"对齐后: {len(common)} 样本")
    return geno, pheno, covariates