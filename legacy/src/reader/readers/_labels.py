# src/reader/readers/_labels.py
"""Shared helper for building unique label mappings.

Every reader that builds a label dict from a list of names uses this
helper. It guarantees that each axis position gets a unique key, so
downstream operators can rebuild the mapping without losing entries.
"""

from __future__ import annotations


def unique_labels(names, dim_name: str, source: str) -> dict[str, int]:
    """Return {name: position}, renaming duplicates with a ``#<position>``
    suffix on the second and later occurrences.
    """
    seen: set[str] = set()
    out: dict[str, int] = {}
    n_dup = 0
    for i, raw in enumerate(names):
        key = str(raw)
        if key in seen:
            n_dup += 1
            key = f"{key}#{i}"
        seen.add(key)
        out[key] = i
    if n_dup:
        print(
            f"  [{source}] renamed {n_dup} duplicate label(s) "
            f"in '{dim_name}'"
        )
    return out