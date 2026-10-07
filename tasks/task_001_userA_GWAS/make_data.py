# tasks/task_001_userA_GWAS/make_data.py
"""二倍体 + 连续表型 + 协变量 + VCF.gz (基线客户)"""

import sys
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

# 参数
PLOIDY = 2
N_SAMPLES = 150
N_SNPS = 5000
SEED = 42
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.5, -0.3, 0.8])
H2 = 0.3
MISSING_RATE = 0.01
HWE_DEV_FRACTION = 0.05


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] 生成基因型 {N_SAMPLES} 样本 × {N_SNPS} SNP (倍性={PLOIDY})")
    geno, mafs = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )

    print(f"[2/5] 注入 HWE 偏离 ({HWE_DEV_FRACTION*100:.0f}% SNP)")
    geno = sim.introduce_hwe_deviation(
        geno, PLOIDY, fraction=HWE_DEV_FRACTION, strength=0.2, seed=SEED,
    )

    print(f"[3/5] 注入缺失 (rate={MISSING_RATE})")
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[4/5] 生成表型 (h2={H2}) 和协变量")
    y = sim.build_phenotype_continuous(geno, CAUSAL_IDX, BETAS, H2, SEED)
    cov = sim.build_covariates(N_SAMPLES, SEED, with_bmi=True)

    print(f"[5/5] 写出文件")
    samples = [f"S{i+1:03d}" for i in range(N_SAMPLES)]
    snp_ids = sim.make_snp_ids(N_SNPS)
    positions = sim.make_positions(N_SNPS, SEED)

    sim.write_vcf(geno, PLOIDY, samples, snp_ids,
                  [CHROM] * N_SNPS, positions,
                  out / "genotype.vcf.gz", compress=True)
    sim.write_phenotype(samples, y, out / "phenotype.csv")
    sim.write_covariates(samples, cov, out / "covariates.csv")

    print(f"\n完成: {N_SAMPLES} 样本 × {N_SNPS} SNP → {out}")


if __name__ == "__main__":
    main()