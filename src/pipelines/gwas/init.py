# src/pipelines/gwas/init.py
"""按命名约定扫描 input/, 生成 input section"""

from pathlib import Path

# 约定名（按优先级）
GENOTYPE_CONVENTION = (
    "genotype.vcf.gz",
    "genotype.vcf",
    "genotype.bed",
)
PHENO_CONVENTION = ("phenotype.csv",)
COVAR_CONVENTION = ("covariates.csv",)


def _match(input_dir: Path, names):
    for name in names:
        p = input_dir / name
        if p.exists():
            return p
    return None


def init_from_input_dir(task_dir):
    """
    约定:
        input/genotype.vcf.gz  或
        input/genotype.vcf     或
        input/genotype.bed     (需 .bim/.fam 同目录)
        input/phenotype.csv
        input/covariates.csv   (可选)
    未命中时列出候选, 用户手改 config.yaml。
    """
    task_dir = Path(task_dir)
    input_dir = task_dir / "input"
    if not input_dir.exists():
        raise FileNotFoundError(f"缺少 input 目录: {input_dir}")

    geno = _match(input_dir, GENOTYPE_CONVENTION)
    pheno = _match(input_dir, PHENO_CONVENTION)
    covar = _match(input_dir, COVAR_CONVENTION)

    def _rel(p):
        return str(p.relative_to(task_dir)) if p else None

    input_section = {
        "genotype":   _rel(geno),
        "phenotype":  _rel(pheno),
        "covariates": _rel(covar),
    }

    print("识别结果:")
    print(f"  基因型:  {geno.name if geno else '(未命中约定名)'}")
    print(f"  表型:    {pheno.name if pheno else '(未命中约定名)'}")
    print(f"  协变量:  {covar.name if covar else '(未命中约定名)'}")

    if geno is None:
        cands = [f.name for f in input_dir.iterdir()
                 if f.suffix.lower() in (".vcf", ".gz", ".bed")]
        if cands:
            print(f"\n  基因型候选: {cands}")
            print(f"  请在 config.yaml 的 input.genotype 手动填写")

    if pheno is None:
        cands = [f.name for f in input_dir.iterdir()
                 if f.suffix.lower() == ".csv"]
        if cands:
            print(f"\n  表型候选: {cands}")
            print(f"  请在 config.yaml 的 input.phenotype 手动填写")

    return input_section