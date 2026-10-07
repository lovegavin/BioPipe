# tasks/task_002_userB_GWAS/make_data.py
"""二倍体 + 连续表型 + 无协变量 + 未压缩 VCF"""

import sys
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

PLOIDY = 2
N_SAMPLES = 200
N_SNPS = 3000
SEED = 43
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.4, -0.35, 0.6])
H2 = 0.3
MISSING_RATE = 0.01
HWE_DEV_FRACTION = 0.05


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 生成基因型 {N_SAMPLES} × {N_SNPS} (倍性={PLOIDY}, 未压缩 VCF)")
    geno, _ = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )
    geno = sim.introduce_hwe_deviation(
        geno, PLOIDY, fraction=HWE_DEV_FRACTION, strength=0.2, seed=SEED,
    )
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[2/4] 生成表型 (无协变量)")
    y = sim.build_phenotype_continuous(geno, CAUSAL_IDX, BETAS, H2, SEED)

    print(f"[3/4] 写出 VCF (未压缩)")
    samples = [f"S{i+1:03d}" for i in range(N_SAMPLES)]
    snp_ids = sim.make_snp_ids(N_SNPS)
    positions = sim.make_positions(N_SNPS, SEED)

    sim.write_vcf(geno, PLOIDY, samples, snp_ids,
                  [CHROM] * N_SNPS, positions,
                  out / "genotype.vcf", compress=False)
    sim.write_phenotype(samples, y, out / "phenotype.csv")

    print(f"[4/4] 完成 → {out} (无 covariates.csv)")


if __name__ == "__main__":
    main()