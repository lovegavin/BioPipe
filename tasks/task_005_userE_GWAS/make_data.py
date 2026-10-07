# tasks/task_005_userE_GWAS/make_data.py
"""四倍体 + 连续表型 + 协变量 + VCF.gz"""

import sys
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

PLOIDY = 4
N_SAMPLES = 120
N_SNPS = 2000
SEED = 46
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.6, -0.4, 0.9])
H2 = 0.3
MISSING_RATE = 0.01


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 生成四倍体基因型 {N_SAMPLES} × {N_SNPS}")
    geno, _ = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )
    # 四倍体不做 HWE 偏离 (流水线跳过 HWE)
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[2/4] 生成连续表型 (h2={H2})")
    y = sim.build_phenotype_continuous(geno, CAUSAL_IDX, BETAS, H2, SEED)

    print(f"[3/4] 生成协变量")
    cov = sim.build_covariates(N_SAMPLES, SEED, with_bmi=False)

    print(f"[4/4] 写出文件")
    samples = [f"S{i+1:03d}" for i in range(N_SAMPLES)]
    snp_ids = sim.make_snp_ids(N_SNPS)
    positions = sim.make_positions(N_SNPS, SEED)

    sim.write_vcf(geno, PLOIDY, samples, snp_ids,
                  [CHROM] * N_SNPS, positions,
                  out / "genotype.vcf.gz", compress=True)
    sim.write_phenotype(samples, y, out / "phenotype.csv")
    sim.write_covariates(samples, cov, out / "covariates.csv")

    print(f"完成 → {out}")
    print(f"  剂量范围: 0~{PLOIDY} (GT 长度为 {PLOIDY})")


if __name__ == "__main__":
    main()