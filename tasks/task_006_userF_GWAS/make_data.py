# tasks/task_006_userF_GWAS/make_data.py
"""四倍体 + 二分类不平衡 + 无协变量 + 未压缩 VCF"""

import sys
from pathlib import Path

import numpy as np

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

PLOIDY = 4
N_SAMPLES = 100
N_CASES = 60
N_SNPS = 1500
SEED = 47
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.9, -0.7, 1.1])
MISSING_RATE = 0.01


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] 生成四倍体基因型 {N_SAMPLES} × {N_SNPS}")
    geno, _ = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[2/4] 生成不平衡二分类表型 (目标 {N_CASES} 病例)")
    y = sim.build_phenotype_binary(geno, CAUSAL_IDX, BETAS, N_CASES, SEED)
    n_case = int(y.sum())
    n_ctrl = N_SAMPLES - n_case
    print(f"  实际病例={n_case}, 对照={n_ctrl}, 比例={n_case/n_ctrl:.2f}")

    print(f"[3/4] 无协变量, 跳过")

    print(f"[4/4] 写出文件 (未压缩 VCF)")
    samples = [f"S{i+1:03d}" for i in range(N_SAMPLES)]
    snp_ids = sim.make_snp_ids(N_SNPS)
    positions = sim.make_positions(N_SNPS, SEED)

    sim.write_vcf(geno, PLOIDY, samples, snp_ids,
                  [CHROM] * N_SNPS, positions,
                  out / "genotype.vcf", compress=False)
    sim.write_phenotype(samples, y, out / "phenotype.csv")

    print(f"完成 → {out} (无 covariates.csv)")
    print(f"  剂量范围: 0~{PLOIDY}, GT 长度为 {PLOIDY}")


if __name__ == "__main__":
    main()