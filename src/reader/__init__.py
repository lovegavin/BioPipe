# src/reader/__init__.py
"""Reader router."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from src.core import ReaderError
from src.reader import readers as _readers_pkg
from src.reader.base import Reader, primary_ext


def _discover() -> dict[str, Reader]:
    registry: dict[str, Reader] = {}
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
                instance = attr()
                for ext in attr.extensions:
                    key = ext.lower()
                    if key in registry:
                        raise ReaderError(
                            f"Extension '{key}' registered by two readers"
                        )
                    registry[key] = instance
    return registry


READERS: dict[str, Reader] = _discover()


def pick_reader(path: Path) -> Reader:
    ext = primary_ext(path)
    if ext not in READERS:
        raise ReaderError(
            f"No reader for extension '{ext}'. "
            f"Available: {sorted(READERS)}"
        )
    return READERS[ext]


__all__ = ["READERS", "pick_reader", "Reader", "primary_ext"]