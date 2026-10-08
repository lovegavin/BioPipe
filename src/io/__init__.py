# src/io/__init__.py
"""IO layer: uniform entry point for reading files into memory forms.

The public function :func:`read` dispatches on ``(role, extension)`` to
the appropriate reader. Callers receive a dictionary of memory forms
keyed by form name.

Examples
--------
>>> from src.io import read
>>> forms = read("input/genotype.vcf.gz", role="genotype")
>>> forms.keys()
dict_keys(['genotype', 'variant_table', 'sample_table'])

>>> forms = read("input/phenotype.csv", role="phenotype")
>>> forms.keys()
dict_keys(['phenotype'])
"""

from __future__ import annotations

import importlib

from src.io.registry import resolve_reader


def read(path: str, role: str, **kwargs) -> dict:
    """Read a file into one or more memory forms.

    Parameters
    ----------
    path : str
        Path to the input file.
    role : str
        One of ``"genotype"``, ``"phenotype"``, ``"covariates"``,
        ``"interval"``, ``"reads"``. Determines the semantic meaning
        of the file and therefore which reader handles it.
    **kwargs
        Additional keyword arguments forwarded to the reader.

    Returns
    -------
    dict
        Mapping of form name to form object. Keys depend on the role:

        * ``genotype``   -> ``{"genotype", "variant_table", "sample_table"}``
        * ``phenotype``  -> ``{"phenotype"}``
        * ``covariates`` -> ``{"covariates"}``

    Raises
    ------
    ReaderFormatError
        If the role is unknown or the extension is unsupported.
    ReaderSchemaError
        If the file's column layout violates the reader contract.
    """
    target = resolve_reader(role, path)
    module_name, func_name = target.split(":")
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    return func(path, **kwargs)


__all__ = ["read"]