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
                from .schemas import builtin_schema
                if attr.parameters_schema is None:
                    attr.parameters_schema = builtin_schema(attr.__name__)
                instances.append(attr())
    return instances


def _from_packages():
    from biopipe.packages import bundled_entries, load_entry
    return [load_entry(descriptor)() for _, descriptor in bundled_entries("reader")]


READERS: list[Reader] = [] if os.getenv("BIOPIPE_REGISTRY_MAINTENANCE") == "1" else _from_packages()


def pick_reader(path: Path) -> Reader:
    """Return the single reader that claims this path.

    Selection is based on the original path (compression suffix
    included), so a ``.bed.gz`` still routes to the correct reader.
    """
    path = Path(path)
    candidates = [r for r in READERS if r.matches(path)]

    if not candidates:
        ext = primary_ext(path)
        from biopipe.file_formats import COMPRESSION_SUFFIXES, compression_extensions
        matching = [r for r in READERS if ext in r.extensions]
        if path.suffix.lower() in COMPRESSION_SUFFIXES and matching and all(
                path.suffix.lower() not in compression_extensions({
                    'file_input': r.file_input, 'handles_compression': r.handles_compression})
                for r in matching):
            raise ReaderError(f"Unsupported compression '{path.suffix}' for {ext} at {path}. "
                              "Use a compression suffix declared by the Reader or decompress the input first.")
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

    # Keep parser-generated indexes in the same disposable directory. Some
    # binary readers generate sidecars, which a single mkstemp file leaked.
    with tempfile.TemporaryDirectory(prefix="biopipe-reader-") as directory:
        tmp_path = Path(directory) / path.with_suffix("").name
        try:
            with _COMPRESSION[suffix](path, "rb") as src, open(tmp_path, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        except (OSError, EOFError, lzma.LZMAError) as exc:
            raise ReaderError(f"Could not decompress {path}: {exc}") from exc
        yield tmp_path


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
    if reader.parameters_schema is not None:
        from biopipe_sdk.protocol import validate_parameters
        args = validate_parameters(reader.parameters_schema, args)

    if reader.handles_compression:
        form = reader.read(path, dims, labels, **args)
    else:
        with _decompressed(path) as real_path:
            form = reader.read(real_path, dims, labels, **args)
    from src.core.contracts import validate_form, validate_output, source_schema
    validate_form(form, reader.output_contract, f"reader {type(reader).__name__} output")
    validate_output(form, source_schema(reader.output_contract, dims), f"reader {type(reader).__name__} output")
    return form


__all__ = [
    "READERS",
    "pick_reader",
    "read_source",
    "Reader",
    "primary_ext",
]
