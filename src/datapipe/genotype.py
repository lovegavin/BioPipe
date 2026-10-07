# src/datapipe/genotype.py
"""基因型读取：VCF / PLINK → GenotypeMatrix"""

from pathlib import Path

import numpy as np
import pandas as pd
import pysam
from bed_reader import open_bed

from src.datapipe.detect import detect_genotype_format
from src.datapipe.memory import GenotypeMatrix


def read_genotype(path, fmt=None) -> GenotypeMatrix:
    """
    统一基因型读取入口。
    path: 文件路径
    fmt:  'vcf' | 'plink' | None (自动探测)
    """
    if fmt is None:
        fmt = detect_genotype_format(path)
    print(f"基因型格式: {fmt}")

    if fmt == "vcf":
        return _read_vcf(path)
    if fmt == "plink":
        return _read_plink(path)
    raise ValueError(f"不支持的基因型格式: {fmt}")


def _read_vcf(path) -> GenotypeMatrix:
    vcf = pysam.VariantFile(path)
    samples = list(vcf.header.samples)
    n_samples = len(samples)

    rows, chroms, positions, snp_ids, refs, alts = [], [], [], [], [], []
    ploidy = None

    for rec in vcf:
        if ploidy is None:
            for s in samples:
                gt = rec.samples[s]["GT"]
                if gt is not None:
                    ploidy = len(gt)
                    break

        row = np.full(n_samples, -1, dtype=np.float32)
        for i, s in enumerate(samples):
            gt = rec.samples[s]["GT"]
            if gt is None or any(a is None for a in gt):
                continue
            row[i] = float(sum(gt))

        chroms.append(rec.chrom)
        positions.append(rec.pos)
        snp_ids.append(rec.id if rec.id else f"{rec.chrom}:{rec.pos}")
        refs.append(rec.ref)
        alts.append(rec.alts[0] if rec.alts else "N")
        rows.append(row)

    vcf.close()

    if ploidy is None:
        raise ValueError(f"无法从 VCF 推断倍性: {path}")
    if not rows:
        raise ValueError(f"VCF 无变异记录: {path}")

    dosage = np.array(rows, dtype=np.float32)
    variant_info = pd.DataFrame({
        "CHROM": chroms, "POS": positions, "ID": snp_ids,
        "REF": refs, "ALT": alts,
    })

    print(f"读取 VCF: {dosage.shape[0]} SNP × {dosage.shape[1]} 样本, 倍性={ploidy}")
    return GenotypeMatrix(
        dosage=dosage,
        variant_info=variant_info,
        sample_ids=samples,
        ploidy=ploidy,
        source_format="vcf",
    )


def _read_plink(bed_path) -> GenotypeMatrix:
    bed_path = Path(bed_path)
    bim_path = bed_path.with_suffix(".bim")
    fam_path = bed_path.with_suffix(".fam")

    for p in (bed_path, bim_path, fam_path):
        if not p.exists():
            raise FileNotFoundError(f"PLINK 文件缺失: {p}")

    bed = open_bed(str(bed_path))
    raw = bed.read(dtype="float32")
    dosage = raw.T
    dosage = np.where(np.isnan(dosage), -1.0, dosage).astype(np.float32)

    bim = pd.read_csv(bim_path, sep=r"\s+", header=None, dtype=str,
                      names=["CHROM", "ID", "CM", "POS", "A1", "A2"])
    variant_info = pd.DataFrame({
        "CHROM": bim["CHROM"].values,
        "POS":   bim["POS"].astype(np.int64).values,
        "ID":    bim["ID"].values,
        "REF":   bim["A2"].values,     # A2 = REF
        "ALT":   bim["A1"].values,     # A1 = ALT
    })

    fam = pd.read_csv(fam_path, sep=r"\s+", header=None, dtype=str,
                      names=["FID", "IID", "PID", "MID", "SEX", "PHENO"])
    sample_ids = fam["IID"].astype(str).tolist()

    print(f"读取 PLINK: {dosage.shape[0]} SNP × {dosage.shape[1]} 样本, 倍性=2")
    return GenotypeMatrix(
        dosage=dosage,
        variant_info=variant_info,
        sample_ids=sample_ids,
        ploidy=2,
        source_format="plink",
    )