"""TSV reader.

Tab-separated two-dimensional tables. This is the CSV reader with a tab
default separator and the ``.tsv`` extension, so ``header``, ``sep``,
``columns``, ``info_columns``, ``encoders`` and all label rules behave
exactly as documented for :class:`CsvReader`.
"""
from __future__ import annotations

from .csv_reader import CsvReader


class TsvReader(CsvReader):
    """Reader for .tsv files."""

    extensions = [".tsv"]
    default_sep = "\t"
    format_name = "TSV"
