# src/reader/base.py
"""Reader abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from src.core import Form


class Reader(ABC):
    """Abstract reader.

    Subclasses declare which extensions they handle, which sibling
    files must or must not exist alongside the target, and whether
    they can consume compressed input directly.

    A reader receives the manifest's ``labels`` block and is
    responsible for producing a Form in which every dim has a label
    mapping. Four label specs are accepted per dim:

        builtin           use the format's built-in label source
        auto              position indices "0", "1", "2", ...
        {<dim>: <pos>}    read position <pos> along <dim>
        {name: pos, ...}  explicit mapping

    A missing dim entry defaults to ``auto``.

    Readers that encode non-numeric columns must record the encoder
    instance used in ``info["encoders"]`` as ``{dim: {label: encoder}}``.
    """

    extensions: ClassVar[list[str]] = []
    requires_siblings: ClassVar[list[str]] = []
    excludes_siblings: ClassVar[list[str]] = []

    # If True, the reader consumes compressed input directly and the
    # framework passes the original path. If False, the framework
    # decompresses to a temporary file first.
    handles_compression: ClassVar[bool] = False

    def matches(self, path: Path) -> bool:
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
    def read(
        self,
        path: Path,
        dims: list,
        labels: dict,
        **args,
    ) -> Form:
        ...


_COMPRESSION = {".gz", ".bz2", ".xz", ".zst"}


def primary_ext(path: Path) -> str:
    p = Path(path)
    if p.suffix.lower() in _COMPRESSION:
        p = p.with_suffix("")
    return p.suffix.lower()


__all__ = ["Reader", "primary_ext"]