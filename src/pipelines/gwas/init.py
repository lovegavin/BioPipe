# src/pipelines/gwas/init.py
"""Scan the task input directory and populate the manifest input section.

No format or schema inspection is performed here — only file existence
is checked against the naming convention. Column-level validation is
the responsibility of readers at run time.
"""

from __future__ import annotations

from pathlib import Path

GENOTYPE_CANDIDATES = (
    "genotype.vcf.gz",
    "genotype.vcf",
    "genotype.bed",
)
PHENOTYPE_CANDIDATES = (
    "phenotype.csv",
    "phenotype.tsv",
    "phenotype.txt",
    "phenotype.xlsx",
    "phenotype.parquet",
)
COVARIATE_CANDIDATES = (
    "covariates.csv",
    "covariates.tsv",
    "covariates.txt",
    "covariates.xlsx",
    "covariates.parquet",
)


def _match(input_dir: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        p = input_dir / name
        if p.exists():
            return p
    return None


def _list_dir(input_dir: Path) -> list[str]:
    return sorted(f.name for f in input_dir.iterdir() if f.is_file())


def init_from_input_dir(task_dir) -> dict:
    """Return the manifest ``input`` section for ``task_dir``.

    Raises
    ------
    FileNotFoundError
        If the input directory is missing, or a mandatory file cannot
        be located under any of the convention names.
    """
    task_dir = Path(task_dir)
    input_dir = task_dir / "input"

    if not input_dir.exists():
        raise FileNotFoundError(
            f"Missing input directory: {input_dir}"
        )

    genotype = _match(input_dir, GENOTYPE_CANDIDATES)
    phenotype = _match(input_dir, PHENOTYPE_CANDIDATES)
    covariates = _match(input_dir, COVARIATE_CANDIDATES)

    if genotype is None:
        raise FileNotFoundError(
            "No genotype file found.\n"
            f"  Expected one of: {list(GENOTYPE_CANDIDATES)}\n"
            f"  Directory listing: {_list_dir(input_dir)}"
        )
    if phenotype is None:
        raise FileNotFoundError(
            "No phenotype file found.\n"
            f"  Expected one of: {list(PHENOTYPE_CANDIDATES)}\n"
            f"  Directory listing: {_list_dir(input_dir)}"
        )

    def _rel(p: Path | None) -> str | None:
        return str(p.relative_to(task_dir)) if p is not None else None

    return {
        "genotype": _rel(genotype),
        "phenotype": _rel(phenotype),
        "covariates": _rel(covariates),
    }