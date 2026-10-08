# src/io/readers/__init__.py
"""Reader implementations.

Each module exposes one or more ``read_<role>`` functions. Readers
receive a file path and return a dictionary of memory forms. All
returned forms must pass their ``validate()`` check before returning.
"""

from src.io.readers import vcf, plink, table  # noqa: F401