# tasks/task_003_userC_GWAS/make_data.py
"""二倍体 + 二分类平衡 (1:1) + 协变量 + VCF.gz"""

import sys
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

PLOIDY = 2
N_SAMPLES = 200
N_CASES = 100
N_SNPS = 3000
SEED = 44
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.7, -0.5, 0.9])   # 二分类效应量更大
MISSING_RATE = 0.01
HWE_DEV_FRACTION = 0.05


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 生成基因型 {N_SAMPLES} × {N_SNPS} (倍性={PLOIDY})")
    geno, _ = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )
    geno = sim.introduce_hwe_deviation(
        geno, PLOIDY, fraction=HWE_DEV_FRACTION, strength=0.2, seed=SEED,
    )
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[2/4] 生成二分类表型 (目标 {N_CASES} 病例)")
    y = sim.build_phenotype_binary(geno, CAUSAL_IDX, BETAS, N_CASES, SEED)
    n_case = int(y.sum())
    n_ctrl = N_SAMPLES - n_case
    print(f"  实际病例={n_case}, 对照={n_ctrl}, 比例={n_case/n_ctrl:.2f}")

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


if __name__ == "__main__":
    main()