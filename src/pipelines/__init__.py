# src/pipelines/__init__.py
"""流水线注册表"""

from src.pipelines import gwas

PIPELINES = {
    "gwas": gwas,
    # 未来: "rnaseq": rnaseq, ...
}