# src/io/registry.py
"""Reader registry: maps ``(role, extension)`` pairs to reader modules.

The registry is the single source of truth for which reader handles
which role and extension combination. Adding a new format means adding
a reader module and one entry here — no changes to pipelines or forms.

Roles
-----
genotype
    Raw genotype matrix. Produces GenotypeMatrix, VariantTable, SampleTable.
phenotype
    Sample-level trait table. Produces Table.
covariates
    Sample-level covariate table. Produces Table.
interval
    Genomic intervals. Reserved.
reads
    Sequencing reads. Reserved.
"""

from __future__ import annotations

from src.core.errors import ReaderFormatError
from src.io.detect import (
    detect_genotype,
    detect_table,
    detect_interval,
)

# --------------------------------------------------------------------- #
# Role definitions
# --------------------------------------------------------------------- #

SUPPORTED_ROLES = (
    "genotype",
    "phenotype",
    "covariates",
    "interval",
    "reads",
)

# Each entry: role -> {parser_key: "module.path:function"}
READER_MAP: dict[str, dict[str, str]] = {
    "genotype": {
        "vcf":   "src.io.readers.vcf:read_vcf",
        "plink": "src.io.readers.plink:read_plink",
    },
    "phenotype": {
        "csv":     "src.io.readers.table:read_phenotype",
        "tsv":     "src.io.readers.table:read_phenotype",
        "excel":   "src.io.readers.table:read_phenotype",
        "parquet": "src.io.readers.table:read_phenotype",
    },
    "covariates": {
        "csv":     "src.io.readers.table:read_covariates",
        "tsv":     "src.io.readers.table:read_covariates",
        "excel":   "src.io.readers.table:read_covariates",
        "parquet": "src.io.readers.table:read_covariates",
    },
    # Reserved roles. Populated once interval and read readers exist.
    "interval": {},
    "reads": {},
}


# --------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------- #

def resolve_reader(role: str, path: str) -> str:
    """Return the ``module:function`` string for the given role and path.

    Parameters
    ----------
    role : str
        One of :data:`SUPPORTED_ROLES`.
    path : str
        Path to the input file. Only the extension is inspected.

    Raises
    ------
    ReaderFormatError
        If the role is unknown, or no reader is registered for the
        detected extension.
    """
    if role not in SUPPORTED_ROLES:
        raise ReaderFormatError(
            f"Unknown reader role: '{role}'\n"
            f"  Supported: {list(SUPPORTED_ROLES)}"
        )

    if role == "genotype":
        parser_key = detect_genotype(path)
    elif role in ("phenotype", "covariates"):
        parser_key = detect_table(path)
    elif role == "interval":
        parser_key = detect_interval(path)
    else:
        raise ReaderFormatError(
            f"Role '{role}' is reserved and not yet implemented."
        )

    registry = READER_MAP.get(role, {})
    if parser_key not in registry:
        raise ReaderFormatError(
            f"No reader registered for role='{role}' "
            f"extension-parser='{parser_key}'\n"
            f"  Path: {path}"
        )
    return registry[parser_key]