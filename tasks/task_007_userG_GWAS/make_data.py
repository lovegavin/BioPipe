# tasks/task_007_userG_GWAS/make_data.py
"""PLINK 格式测试客户: 从 task_001 的合成数据生成 PLINK 文件"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from bed_reader import open_bed

TASK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK_DIR.parent))

from _common import sim

PLOIDY = 2
N_SAMPLES = 80
N_SNPS = 1000
SEED = 48
CHROM = "chr22"
CAUSAL_IDX = [0, 1, 2]
BETAS = np.array([0.5, -0.3, 0.8])
H2 = 0.3
MISSING_RATE = 0.01


def write_plink(geno, snp_ids, positions, samples, out_prefix):
    """手写 PLINK .bed/.bim/.fam (SNP-major 编码)"""
    out_prefix = Path(out_prefix)

    # .fam
    pd.DataFrame({
        "FID": samples, "IID": samples,
        "PID": 0, "MID": 0, "SEX": 0, "PHENO": -9,
    }).to_csv(f"{out_prefix}.fam", sep=" ", header=False, index=False)

    # .bim
    pd.DataFrame({
        "CHR": [CHROM] * len(snp_ids),
        "SNP": snp_ids,
        "CM": 0,
        "BP": positions,
        "A1": "A",
        "A2": "G",
    }).to_csv(f"{out_prefix}.bim", sep="\t", header=False, index=False)

    # .bed (SNP-major, 每样本 2 bit)
    n_snps, n_samples = geno.shape
    n_bytes = (n_samples + 3) // 4
    code_map = {0: 0b00, 1: 0b10, 2: 0b11, -1: 0b01}

    buf = bytearray(b"\x6c\x1b\x01")
    for j in range(n_snps):
        row_bytes = bytearray(n_bytes)
        for i in range(n_samples):
            code = code_map.get(int(geno[j, i]), 0b01)
            row_bytes[i // 4] |= (code << ((i % 4) * 2))
        buf.extend(row_bytes)

    with open(f"{out_prefix}.bed", "wb") as f:
        f.write(bytes(buf))


def main():
    out = TASK_DIR / "input"
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] 生成基因型 {N_SAMPLES} × {N_SNPS} (PLINK 输出)")
    geno, _ = sim.generate_genotypes(
        N_SAMPLES, N_SNPS, PLOIDY, SEED,
        block_size=100, r2_start=0.9, r2_end=0.1,
    )
    geno = sim.introduce_missing(geno, PLOIDY, rate=MISSING_RATE, seed=SEED)

    print(f"[2/3] 生成表型")
    y = sim.build_phenotype_continuous(geno, CAUSAL_IDX, BETAS, H2, SEED)

    print(f"[3/3] 写出 PLINK + 表型")
    samples = [f"S{i+1:03d}" for i in range(N_SAMPLES)]
    snp_ids = sim.make_snp_ids(N_SNPS)
    positions = sim.make_positions(N_SNPS, SEED)

    write_plink(geno, snp_ids, positions, samples, out / "genotype")
    sim.write_phenotype(samples, y, out / "phenotype.csv")

    print(f"完成 → {out}")
    print(f"  文件: genotype.bed / .bim / .fam")


if __name__ == "__main__":
    main()