# src/io/readers/table.py
"""CSV / TSV / Excel / Parquet readers for phenotype and covariate tables.

Hard-coded column contract
--------------------------
phenotype
    Column 1 must be named ``sample_id``.
    Column 2 must be named ``trait_value``.
    No further columns are allowed.

covariates
    Column 1 must be named ``sample_id``.
    All remaining columns are treated as covariates; names are free.

Any deviation raises :class:`ReaderSchemaError` with an explicit
expectation/actual diff.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core.errors import ReaderSchemaError
from src.core.forms import Table
from src.io.detect import detect_table, split_compression

PHENOTYPE_COLUMNS = ("sample_id", "trait_value")
SAMPLE_ID_COLUMN = "sample_id"


# --------------------------------------------------------------------- #
# Low-level loaders
# --------------------------------------------------------------------- #

def _load_raw(path: str) -> pd.DataFrame:
    """Dispatch to the pandas loader implied by the extension."""
    fmt = detect_table(path)
    _, comp = split_compression(path)

    if fmt == "csv":
        df = pd.read_csv(path)
    elif fmt == "tsv":
        df = pd.read_csv(path, sep="\t")
    elif fmt == "excel":
        # Compression is rejected upstream by detect_table.
        df = pd.read_excel(path, engine="openpyxl")
    elif fmt == "parquet":
        df = pd.read_parquet(path)
    else:
        # Unreachable: detect_table only returns the four keys above.
        raise ValueError(f"Unhandled table format: {fmt}")

    return df


def _check_columns(df: pd.DataFrame, expected: tuple, path: str) -> None:
    """Raise :class:`ReaderSchemaError` if the first columns deviate."""
    actual = tuple(df.columns[: len(expected)])
    if actual != expected:
        raise ReaderSchemaError(
            path=path,
            expected=list(expected),
            actual=list(df.columns),
            hint=(
                "Rename the first columns to match the contract. "
                "See docs/input_spec.md for details."
            ),
        )


def _set_sample_index(df: pd.DataFrame) -> pd.DataFrame:
    """Set ``sample_id`` as the index with string dtype."""
    df = df.set_index(SAMPLE_ID_COLUMN)
    df.index = df.index.astype(str)
    df.index.name = SAMPLE_ID_COLUMN
    return df


# --------------------------------------------------------------------- #
# Public readers
# --------------------------------------------------------------------- #

def read_phenotype(path: str) -> dict:
    """Read a phenotype table.

    Returns
    -------
    dict
        ``{"phenotype": Table}``
    """
    df = _load_raw(path)
    _check_columns(df, PHENOTYPE_COLUMNS, path)

    if df.shape[1] != len(PHENOTYPE_COLUMNS):
        raise ReaderSchemaError(
            path=path,
            expected=list(PHENOTYPE_COLUMNS),
            actual=list(df.columns),
            hint=(
                f"Phenotype files must contain exactly "
                f"{len(PHENOTYPE_COLUMNS)} columns."
            ),
        )

    df = _set_sample_index(df)
    table = Table(data=df, index_name=SAMPLE_ID_COLUMN,
                  source_format=detect_table(path))
    table.validate()

    print(f"[table] phenotype: {table.shape[0]} samples")
    return {"phenotype": table}


def read_covariates(path: str) -> dict:
    """Read a covariate table.

    Returns
    -------
    dict
        ``{"covariates": Table}``
    """
    df = _load_raw(path)

    if df.shape[1] < 2:
        raise ReaderSchemaError(
            path=path,
            expected=[SAMPLE_ID_COLUMN, "<at least one covariate>"],
            actual=list(df.columns),
            hint="Covariate files need at least one covariate column.",
        )

    if df.columns[0] != SAMPLE_ID_COLUMN:
        raise ReaderSchemaError(
            path=path,
            expected=[SAMPLE_ID_COLUMN, "..."],
            actual=list(df.columns),
            hint="First column must be named 'sample_id'.",
        )

    df = _set_sample_index(df)
    table = Table(data=df, index_name=SAMPLE_ID_COLUMN,
                  source_format=detect_table(path))
    table.validate()

    print(
        f"[table] covariates: {table.shape[0]} samples x "
        f"{table.shape[1]} columns"
    )
    return {"covariates": table}