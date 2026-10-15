# src/reader/base.py
"""Reader abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from src.core import Form
from biopipe.file_formats import COMPRESSION_SUFFIXES, compression_extensions, uncompressed_path


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

    output_contract: ClassVar[dict | None] = None
    version: ClassVar[str] = "1.0.0"
    dependencies: ClassVar[list[str] | None] = None
    dependency_imports: ClassVar[list[str] | None] = None
    parameters_schema: ClassVar[dict | None] = None

    extensions: ClassVar[list[str]] = []
    requires_siblings: ClassVar[list[str]] = []
    excludes_siblings: ClassVar[list[str]] = []

    # If True, the reader consumes compressed input directly and the
    # framework passes the original path. If False, the framework
    # decompresses to a temporary file first.
    handles_compression: ClassVar[bool] = False

    # Declarative Studio import hints. No optional parser is loaded to inspect these.
    # Compression defaults to the framework's gzip/bzip2/xz wrapper for readers
    # that do not handle compression themselves; native readers opt in explicitly.
    file_input: ClassVar[dict | None] = None

    supports_disk_read: ClassVar[bool] = False
    disk_protocol: ClassVar[str | None] = None

    def probe(self, path: Path, **args) -> dict:
        """Inspect metadata only. File bytes are never treated as RAM bytes."""
        return {"file_bytes": Path(path).stat().st_size, "dense_bytes": None}

    def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
        """Write numeric blocks into writer and return Form metadata, without data."""
        raise NotImplementedError

    def matches(self, path: Path) -> bool:
        ext = primary_ext(path)
        if ext not in self.extensions:
            return False
        suffix = path.suffix.lower()
        if suffix in COMPRESSION_SUFFIXES and suffix not in compression_extensions({
                'file_input': self.file_input, 'handles_compression': self.handles_compression}):
            return False
        path = uncompressed_path(path)
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


def primary_ext(path: Path) -> str:
    return uncompressed_path(path).suffix.lower()


__all__ = ["Reader", "primary_ext"]
