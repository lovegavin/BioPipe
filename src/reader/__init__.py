# src/reader/__init__.py
"""Reader router and unified entry point.

Callers go through ``read_source``. It selects the reader by the
original path, decompresses if the reader cannot handle compression,
and dispatches.
"""

from __future__ import annotations

import bz2
import gzip
import importlib
import lzma
import os
import pkgutil
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from src.core import ReaderError
from src.reader import readers as _readers_pkg
from src.reader.base import Reader, primary_ext


_COMPRESSION = {
    ".gz": gzip.open,
    ".bz2": bz2.open,
    ".xz": lzma.open,
}


def _discover() -> list[Reader]:
    instances: list[Reader] = []
    for _, mod_name, is_pkg in pkgutil.iter_modules(_readers_pkg.__path__):
        if is_pkg:
            continue
        mod = importlib.import_module(f"src.reader.readers.{mod_name}")
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, Reader)
                and attr is not Reader
                and getattr(attr, "extensions", None)
            ):
                instances.append(attr())
    return instances


READERS: list[Reader] = _discover()


def pick_reader(path: Path) -> Reader:
    """Return the single reader that claims this path.

    Selection is based on the original path (compression suffix
    included), so a ``.bed.gz`` still routes to the correct reader.
    """
    path = Path(path)
    candidates = [r for r in READERS if r.matches(path)]

    if not candidates:
        ext = primary_ext(path)
        known = sorted({e for r in READERS for e in r.extensions})
        raise ReaderError(
            f"No reader for extension '{ext}' at {path}. "
            f"Known extensions: {known}"
        )
    if len(candidates) > 1:
        names = [type(r).__name__ for r in candidates]
        raise ReaderError(
            f"Multiple readers claim {path}: {names}."
        )
    return candidates[0]


@contextmanager
def _decompressed(path: Path):
    """If ``path`` has a compression suffix and is not already handled
    by the reader, decompress it to a temporary file that keeps the
    original stem and primary extension.
    """
    suffix = path.suffix.lower()
    if suffix not in _COMPRESSION:
        yield path
        return

    real_suffix = path.with_suffix("").suffix
    fd, tmp_name = tempfile.mkstemp(suffix=real_suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        opener = _COMPRESSION[suffix]
        with opener(path, "rb") as src, open(tmp_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)


def read_source(
    path: Path,
    dims: list,
    labels: dict,
    **args,
):
    """Read a source file into a Form.

    Handles compression once, at the entry point, so individual
    readers only ever see plain files unless they declare
    ``handles_compression = True``.
    """
    path = Path(path)
    reader = pick_reader(path)

    if reader.handles_compression:
        return reader.read(path, dims, labels, **args)

    with _decompressed(path) as real_path:
        return reader.read(real_path, dims, labels, **args)


__all__ = [
    "READERS",
    "pick_reader",
    "read_source",
    "Reader",
    "primary_ext",
]