# src/datapipe/detect.py
"""文件类型检测（业务无关）"""

from pathlib import Path


def detect_table_format(path) -> str:
    """返回 'csv' | 'tsv' | 'excel'"""
    p = str(path).lower()
    if p.endswith(".csv"):
        return "csv"
    if p.endswith((".tsv", ".txt")):
        return "tsv"
    if p.endswith((".xlsx", ".xls")):
        return "excel"
    raise ValueError(f"无法识别的表格格式: {path}")


def detect_genotype_format(path) -> str:
    """
    返回 'vcf' | 'plink'
    扩展名优先, 文件头兜底。
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"基因型文件不存在: {path}")

    name = str(p).lower()

    # 扩展名优先
    if name.endswith((".vcf", ".vcf.gz")):
        return "vcf"
    if name.endswith(".bed"):
        return "plink"

    # 文件头兜底
    with open(p, "rb") as f:
        head = f.read(16)

    if head.startswith(b"##fileformat=VCF"):
        return "vcf"
    if head[:3] == b"\x6c\x1b\x01":   # PLINK .bed 魔数
        return "plink"

    raise ValueError(f"无法识别的基因型格式: {path}")


def detect_vcf(path) -> bool:
    """兼容旧接口: 是否 VCF"""
    try:
        return detect_genotype_format(path) == "vcf"
    except Exception:
        return False