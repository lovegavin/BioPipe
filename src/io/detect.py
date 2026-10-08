# src/io/detect.py
"""File format detection based on file extensions only.

Design principles
-----------------
* Only the file extension determines the parser. No header sniffing,
  no magic bytes, no content inspection. This keeps detection fast,
  predictable and robust against truncated or remote files.
* Compression suffixes (``.gz``, ``.bz2``, ``.xz``, ``.zst``) are
  stripped before inspecting the primary extension. A compressed
  ``.csv.gz`` is still a CSV.
* An unrecognized extension raises :class:`ReaderFormatError` with the
  full list of supported extensions.
"""

from __future__ import annotations

from pathlib import Path

from src.core.errors import ReaderFormatError

# --------------------------------------------------------------------- #
# Extension tables
# --------------------------------------------------------------------- #

# Compression suffixes stripped before primary extension inspection.
COMPRESSION_EXT = {".gz", ".bz2", ".xz", ".zst"}

# Primary extension -> parser key for genotype files.
GENOTYPE_EXT = {
    ".vcf": "vcf",
    ".bed": "plink",
}

# Primary extension -> parser key for tabular files.
TABLE_EXT = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "tsv",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
}

# Primary extension -> parser key for genomic intervals.
INTERVAL_EXT = {
    ".bed": "bed",
    ".gtf": "gtf",
    ".gff": "gtf",
    ".gff3": "gtf",
}

# Formats that do not tolerate a compression suffix.
NO_COMPRESSION = {"excel", "parquet"}


# --------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------- #

def split_compression(path) -> tuple[Path, str | None]:
    """Strip a trailing compression suffix if present.

    Parameters
    ----------
    path : str or Path

    Returns
    -------
    (base_path, compression)
        ``base_path`` has the compression suffix removed.
        ``compression`` is the suffix without the dot, or ``None``.

    Examples
    --------
    >>> split_compression("a.vcf.gz")
    (PosixPath('a.vcf'), 'gz')
    >>> split_compression("a.csv")
    (PosixPath('a.csv'), None)
    """
    p = Path(path)
    if p.suffix.lower() in COMPRESSION_EXT:
        return p.with_suffix(""), p.suffix.lower()[1:]
    return p, None


def _primary_ext(path) -> tuple[str, str | None]:
    """Return ``(primary_extension, compression)`` for a path."""
    base, comp = split_compression(path)
    return base.suffix.lower(), comp


def detect_genotype(path) -> str:
    """Detect the parser key for a genotype file.

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ReaderFormatError
        If the primary extension is not supported.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext, _ = _primary_ext(p)
    if ext not in GENOTYPE_EXT:
        raise ReaderFormatError(
            f"Unrecognized genotype extension: '{ext}'\n"
            f"  Path:     {path}\n"
            f"  Supported: {sorted(GENOTYPE_EXT.keys())}\n"
            f"  Note:     compression suffixes {sorted(COMPRESSION_EXT)} "
            f"are stripped automatically."
        )
    return GENOTYPE_EXT[ext]


def detect_table(path) -> str:
    """Detect the parser key for a tabular file.

    Raises
    ------
    ReaderFormatError
        If the primary extension is not supported, or if the extension
        does not permit a compression suffix but one was provided.
    """
    ext, comp = _primary_ext(path)
    if ext not in TABLE_EXT:
        raise ReaderFormatError(
            f"Unrecognized table extension: '{ext}'\n"
            f"  Path:     {path}\n"
            f"  Supported: {sorted(TABLE_EXT.keys())}\n"
            f"  Note:     compression suffixes {sorted(COMPRESSION_EXT)} "
            f"are stripped automatically."
        )

    fmt = TABLE_EXT[ext]
    if comp and fmt in NO_COMPRESSION:
        raise ReaderFormatError(
            f"Format '{fmt}' does not support compression: '{path}'\n"
            f"  Remove the '.{comp}' suffix or convert to CSV/TSV."
        )
    return fmt


def detect_interval(path) -> str:
    """Detect the parser key for a genomic interval file.

    Reserved for future interval readers (BED / GTF).
    """
    ext, _ = _primary_ext(path)
    if ext not in INTERVAL_EXT:
        raise ReaderFormatError(
            f"Unrecognized interval extension: '{ext}'\n"
            f"  Path:     {path}\n"
            f"  Supported: {sorted(INTERVAL_EXT.keys())}"
        )
    return INTERVAL_EXT[ext]