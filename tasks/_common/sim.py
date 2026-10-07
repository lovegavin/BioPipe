# tasks/_common/sim.py
"""合成数据生成: LD 结构 + HWE 偏离 + 缺失 + VCF 写入"""

from pathlib import Path

import numpy as np
import pandas as pd
import pysam


# ---------- 基因型 ----------
def generate_genotypes(n_samples, n_snps, ploidy, seed,
                       maf_min=0.05, maf_max=0.5,
                       block_size=100, r2_start=0.9, r2_end=0.1):
    """
    生成带 LD block 结构的剂量矩阵。
    每个 block 内 SNP 共享隐变量 z，通过概率继承产生相关。
    返回: (geno (n_snps, n_samples) int8, mafs (n_snps,))
    """
    rng = np.random.default_rng(seed)
    geno = np.zeros((n_snps, n_samples), dtype=np.int8)
    mafs = np.zeros(n_snps, dtype=float)

    n_blocks = (n_snps + block_size - 1) // block_size
    for b in range(n_blocks):
        start = b * block_size
        end = min(start + block_size, n_snps)
        size = end - start

        maf_base = rng.uniform(maf_min, maf_max)
        z = rng.binomial(ploidy, maf_base, n_samples).astype(np.int8)

        for k in range(size):
            idx = start + k
            frac = k / max(size - 1, 1)
            r2 = r2_start + (r2_end - r2_start) * frac
            inherit_prob = np.sqrt(max(r2, 0.0))

            maf_snp = rng.uniform(maf_min, maf_max)
            independent = rng.binomial(ploidy, maf_snp, n_samples).astype(np.int8)
            inherit_mask = rng.random(n_samples) < inherit_prob
            geno[idx] = np.where(inherit_mask, z, independent)
            mafs[idx] = maf_snp

    return geno, mafs


def introduce_hwe_deviation(geno, ploidy, fraction=0.05,
                             strength=0.2, seed=0):
    """
    对指定比例的 SNP 引入 HWE 偏离（减少杂合子）。
    只对二倍体有定义。多倍体直接返回原矩阵。
    """
    if ploidy != 2:
        return geno

    rng = np.random.default_rng(seed + 999)
    n_snps = geno.shape[0]
    n_deviate = int(fraction * n_snps)
    if n_deviate == 0:
        return geno

    deviated_idx = rng.choice(n_snps, n_deviate, replace=False)
    for idx in deviated_idx:
        row = geno[idx]
        het_mask = row == 1
        n_het = int(het_mask.sum())
        n_change = int(n_het * strength)
        if n_change == 0:
            continue
        het_positions = np.where(het_mask)[0]
        change_pos = rng.choice(het_positions, n_change, replace=False)
        # 一半改 0, 一半改 2
        for i, pos in enumerate(change_pos):
            row[pos] = 0 if i % 2 == 0 else 2

    return geno


def introduce_missing(geno, ploidy, rate=0.01, seed=0):
    """随机置缺失: 剂量矩阵中标记 -1"""
    rng = np.random.default_rng(seed + 777)
    mask = rng.random(geno.shape) < rate
    geno[mask] = -1
    return geno


# ---------- 表型 ----------
def build_phenotype_continuous(geno, causal_idx, betas, h2, seed):
    """y = G_causal·β + ε, 遗传力 = h2"""
    rng = np.random.default_rng(seed + 100)
    # geno 形状 (n_snps, n_samples); 因果 SNP 取行, 转置成 (n_samples, n_causal)
    g = geno[causal_idx, :].T.astype(float)
    g[g < 0] = 0
    genetic = g @ betas
    var_g = np.var(genetic)
    if var_g < 1e-8:
        raise ValueError("遗传方差过小")
    noise_scale = np.sqrt(var_g * (1 - h2) / h2)
    return genetic + rng.normal(0, noise_scale, geno.shape[1])


def build_phenotype_binary(geno, causal_idx, betas, n_cases, seed):
    """logistic 模型, 二分法调截距使病例数 ≈ n_cases"""
    rng = np.random.default_rng(seed + 200)
    g = geno[causal_idx, :].T.astype(float)
    g[g < 0] = 0
    linear = g @ betas

    lo, hi = -20.0, 20.0
    for _ in range(50):
        mid = (lo + hi) / 2
        prob = 1 / (1 + np.exp(-(linear + mid)))
        n = int(rng.binomial(1, prob).sum())
        if n < n_cases:
            lo = mid
        else:
            hi = mid
    prob = 1 / (1 + np.exp(-(linear + (lo + hi) / 2)))
    return rng.binomial(1, prob)


# ---------- 协变量 ----------
def build_covariates(n_samples, seed, with_bmi=False):
    rng = np.random.default_rng(seed + 300)
    df = pd.DataFrame({
        "age": np.clip(rng.normal(55, 12, n_samples), 18, 80).astype(int),
        "sex": rng.integers(0, 2, n_samples),
    })
    if with_bmi:
        df["BMI"] = np.round(rng.normal(25, 4, n_samples), 1)
    return df


# ---------- 写出 ----------
def write_vcf(geno, ploidy, samples, snp_ids, chroms, positions,
              out_path, compress=True):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = pysam.VariantHeader()
    header.add_meta("fileformat", value="VCFv4.2")
    header.add_meta("source", value="synthetic_sim")

    seen = []
    for c in chroms:
        if c not in seen:
            seen.append(c)
            header.contigs.add(c, length=200_000_000)
    header.add_line(
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">'
    )
    for s in samples:
        header.add_sample(s)

    mode = "wz" if compress else "w"
    with pysam.VariantFile(str(out_path), mode, header=header) as vcf:
        for j in range(geno.shape[0]):
            rec = vcf.new_record(
                contig=str(chroms[j]),
                start=int(positions[j]) - 1,
                stop=int(positions[j]),
                alleles=("A", "G"),
                id=str(snp_ids[j]),
            )
            for i, s in enumerate(samples):
                d = int(geno[j, i])
                if d < 0:
                    rec.samples[s]["GT"] = tuple([None] * ploidy)
                else:
                    rec.samples[s]["GT"] = tuple([1] * d + [0] * (ploidy - d))
            vcf.write(rec)


def i_idx(j, i):
    return j


def write_phenotype(samples, y, path):
    pd.DataFrame({"sample_id": samples, "trait_value": y}).to_csv(
        path, index=False
    )


def write_covariates(samples, cov_df, path):
    out = cov_df.copy()
    out.insert(0, "sample_id", samples)
    out.to_csv(path, index=False)


def make_snp_ids(n_snps, prefix="rs"):
    return [f"{prefix}{j+1:06d}" for j in range(n_snps)]


def make_positions(n_snps, seed, chrom_len=50_000_000, min_gap=100):
    rng = np.random.default_rng(seed + 1)
    max_start = chrom_len - n_snps * min_gap
    starts = np.sort(rng.choice(max_start, n_snps, replace=False))
    return (starts + np.arange(n_snps) * min_gap + 1).astype(int)