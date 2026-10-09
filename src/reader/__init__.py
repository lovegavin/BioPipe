# src/reader/__init__.py
"""Reader router."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from src.core import ReaderError
from src.reader import readers as _readers_pkg
from src.reader.base import Reader, primary_ext


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

    Raises
    ------
    ReaderError
        If no reader matches, or if more than one reader claims the
        same path.
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
            f"Multiple readers claim {path}: {names}. "
            f"Disambiguate by adding required siblings or renaming."
        )
    return candidates[0]


__all__ = ["READERS", "pick_reader", "Reader", "primary_ext"]