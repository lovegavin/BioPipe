# src/reader/base.py
"""Reader abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from src.core import Form

_COMPRESSION = {".gz", ".bz2", ".xz", ".zst"}


class Reader(ABC):
    """Abstract reader.

    Subclasses declare which extensions they handle via the
    ``extensions`` class attribute, and implement ``read``.
    """

    extensions: ClassVar[list[str]] = []

    @abstractmethod
    def read(
        self,
        path: Path,
        dims: list,
        labels: dict,
        **args,
    ) -> Form:
        """Turn a file into a Form.

        Parameters
        ----------
        path : Path
            File to read.
        dims : list[str]
            Axis names in order.
        labels : dict
            ``{dim_name: {label: position}}``. Positions are 0-based
            indices within ``data``.
        **args
            Reader-specific arguments from the manifest's ``args``
            section.

        Returns
        -------
        Form
        """
        ...


def primary_ext(path: Path) -> str:
    p = Path(path)
    if p.suffix.lower() in _COMPRESSION:
        p = p.with_suffix("")
    return p.suffix.lower()