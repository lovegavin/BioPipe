# src/datapipe/memory.py
"""统一内存形式定义。

每种内存形式对应一类物理数据:
    GenotypeMatrix   — 位点 × 样本的基因型计数 (VCF / PLINK / BGEN / ...)
    Table            — 任意二维表格 (CSV / TSV / Excel)
未来扩展:
    ExpressionMatrix — 基因 × 样本的表达量 (count / 10x / ...)
    IntervalTable    — 基因组区间 (BED / GTF / GFF)
    SequenceReads    — 测序读段路径 (FASTQ / BAM)
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class GenotypeMatrix:
    """基因型矩阵。dosage 形状 (n_snps, n_samples)，缺失 = -1。"""
    dosage: np.ndarray
    variant_info: pd.DataFrame
    sample_ids: list
    ploidy: int
    source_format: str = "unknown"

    @property
    def n_snps(self) -> int:
        return int(self.dosage.shape[0])

    @property
    def n_samples(self) -> int:
        return int(self.dosage.shape[1])

    def subset_samples(self, indices) -> "GenotypeMatrix":
        """按列索引子集/重排样本。"""
        indices = list(indices)
        return GenotypeMatrix(
            dosage=self.dosage[:, indices],
            variant_info=self.variant_info.reset_index(drop=True),
            sample_ids=[self.sample_ids[i] for i in indices],
            ploidy=self.ploidy,
            source_format=self.source_format,
        )

    def subset_snps(self, mask) -> "GenotypeMatrix":
        """按行掩码过滤 SNP。"""
        mask = np.asarray(mask, dtype=bool)
        return GenotypeMatrix(
            dosage=self.dosage[mask],
            variant_info=self.variant_info[mask].reset_index(drop=True),
            sample_ids=list(self.sample_ids),
            ploidy=self.ploidy,
            source_format=self.source_format,
        )


@dataclass
class Table:
    """通用二维表格。第一列已设为 index（样本 ID 或类似）。"""
    data: pd.DataFrame
    source_format: str = "unknown"

    def __getattr__(self, name):
        # 转发所有未定义属性到 pd.DataFrame, 保持 DataFrame 使用习惯
        if name in ("data", "source_format"):
            raise AttributeError(name)
        return getattr(self.data, name)

    def subset_rows(self, sample_ids) -> "Table":
        """按样本 ID 子集/重排。"""
        return Table(
            data=self.data.loc[sample_ids],
            source_format=self.source_format,
        )