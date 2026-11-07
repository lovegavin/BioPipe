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
from src.reader.base import Reader, primary_ext


_COMPRESSION = {
    ".gz": gzip.open,
    ".bz2": bz2.open,
    ".xz": lzma.open,
}


def _from_packages():
    from operon.packages import bundled_entries, load_entry
    from operon.lazy import reader_proxy
    return [reader_proxy(d, lambda d=d: load_entry(d)) for _, d in bundled_entries("reader")]


READERS: list[Reader] = [] if os.getenv("OPERON_REGISTRY_MAINTENANCE") == "1" else _from_packages()


def _output_kind(reader) -> str:
    """Return the declared output kind of a reader (form by default)."""
    declaration = getattr(reader, "_declaration", None) or getattr(reader, "definition", {}) or {}
    contracts = declaration.get("contracts") or {}
    output = contracts.get("output") or {}
    return str(output.get("kind") or "form")


def pick_reader(path: Path, name: str | None = None) -> Reader:
    """Return an explicitly named Reader, or the single Reader claiming a path.

    Selection is based on the original path (compression suffix
    included), so a ``.bed.gz`` still routes to the correct reader. An explicit
    registered ID bypasses suffix inference, but keeps compression and required
    companion checks. Reader parameters remain independent of this selector.
    """
    path = Path(path)
    if name is not None:
        from operon.reader_selection import candidates as select
        descriptors = [{**getattr(reader, '_declaration', {}),
                        'id': getattr(reader, '_declaration', {}).get('id', type(reader).__name__),
                        **{key: getattr(reader, key) for key in ('extensions', 'requires_siblings', 'excludes_siblings', 'handles_compression', 'file_input')}}
                       for reader in READERS]
        try:
            selected = select(descriptors, path, name, check_siblings=True)
        except ValueError as exc:
            raise ReaderError(str(exc)) from exc
        if not selected:
            raise ReaderError(f'Reader {name} cannot read {path}: unsupported compression or missing required companion files')
        return READERS[descriptors.index(selected[0])]
    candidates = [r for r in READERS if r.matches(path)]

    if not candidates:
        ext = primary_ext(path)
        from operon.file_formats import COMPRESSION_SUFFIXES, compression_extensions
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
    if candidates and all(_output_kind(reader) == "file" for reader in candidates):
        ext = primary_ext(path)
        if any(_output_kind(reader) != "file" and ext in reader.extensions for reader in READERS):
            raise ReaderError(
                f"Unsupported compression '{path.suffix}' for {ext} at {path}. "
                "Use a compression suffix declared by the Reader or decompress the input first."
            )
    if len(candidates) > 1:
        # A metadata-only file reader (contracts.output.kind == "file") shares
        # its suffix with the typed reader that decodes the same format.
        # Automatic selection keeps returning typed data; file readers are
        # chosen only when a caller asks for them by id.
        typed = [r for r in candidates if _output_kind(r) != "file"]
        if len(typed) == 1:
            return typed[0]
        if typed:
            candidates = typed
        else:
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
    with tempfile.TemporaryDirectory(prefix="operon-reader-") as directory:
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
    *,
    reader_id: str | None = None,
    **args,
):
    """Read a source file into a Form.

    Handles compression once, at the entry point, so individual
    readers only ever see plain files unless they declare
    ``handles_compression = True``.
    """
    path = Path(path)
    reader = pick_reader(path, reader_id)
    if reader.parameters_schema is None:
        raise ReaderError("Protocol v3 requires a Reader parameter schema; migrate the declaration first")
    from operon_sdk.protocol import validate_parameters
    args = validate_parameters(reader.parameters_schema, args)

    if reader.handles_compression:
        form = reader.read(path, dims, labels, **args)
    else:
        with _decompressed(path) as real_path:
            form = reader.read(real_path, dims, labels, **args)
    from operon_sdk.native_array import reader_output
    form = reader_output(form, getattr(reader, "_declaration", {}) or getattr(reader, "definition", {}))
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
