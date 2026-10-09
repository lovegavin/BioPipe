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

    Subclasses declare:

    * ``extensions`` — extensions this reader handles.
    * ``requires_siblings`` — extensions that must exist alongside the
      target file for this reader to claim it.
    * ``excludes_siblings`` — extensions that must NOT exist alongside
      the target file for this reader to claim it.

    The two sibling rules disambiguate readers that share an extension.
    """

    extensions: ClassVar[list[str]] = []
    requires_siblings: ClassVar[list[str]] = []
    excludes_siblings: ClassVar[list[str]] = []

    def matches(self, path: Path) -> bool:
        """Return True if this reader claims ``path``."""
        ext = primary_ext(path)
        if ext not in self.extensions:
            return False
        for sib_ext in self.requires_siblings:
            if not path.with_suffix(sib_ext).exists():
                return False
        for sib_ext in self.excludes_siblings:
            if path.with_suffix(sib_ext).exists():
                return False
        return True

    @abstractmethod
    def read(self, path: Path, dims, labels, **args) -> Form:
        ...


def primary_ext(path: Path) -> str:
    p = Path(path)
    if p.suffix.lower() in _COMPRESSION:
        p = p.with_suffix("")
    return p.suffix.lower()