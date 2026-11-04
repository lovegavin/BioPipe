"""Shared helpers for protein sequence and structure operators."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def column_index(form: Form, field_dim: str, name: str) -> int:
    """Return the position of a named field column, or -1 when absent."""
    labels = form.labels.get(field_dim)
    if not labels:
        return -1
    for label, position in labels.items():
        if label == name:
            return int(position)
    return -1


def has_column(form: Form, field_dim: str, name: str) -> bool:
    return column_index(form, field_dim, name) >= 0


def _format_number(value) -> str:
    if value is None:
        return "_"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(number):
        return "_"
    if number.is_integer():
        return str(int(number))
    return format(number, ".10g")


def decode_column(form: Form, field_dim: str, name: str) -> np.ndarray | None:
    """Decode one structural column to strings.

    Label-encoded columns are inverted with the encoder recorded in
    ``form.info["encoders"]``; numeric columns are formatted without a
    trailing ``.0`` so residue numbers compare with PDB text.
    """
    index = column_index(form, field_dim, name)
    if index < 0:
        return None
    values = np.asarray(form.data)[:, index]
    encoders = (form.info.get("encoders") or {}).get(field_dim) or {}
    encoder = encoders.get(name)
    if encoder is not None:
        return np.array([str(v) for v in encoder.inverse_transform(values)], dtype=object)
    return np.array([_format_number(v) for v in values], dtype=object)


def _clean(value: str) -> str:
    text = str(value).strip()
    return "_" if text == "" else text


def residue_labels(form: Form, field_dim: str) -> np.ndarray:
    """Build ``chain:resname:number`` labels for every atom row."""
    chain = decode_column(form, field_dim, "chain")
    resname = decode_column(form, field_dim, "resname")
    number = decode_column(form, field_dim, "residue_number")
    if chain is None or resname is None or number is None:
        raise StepError(
            "structure form must carry chain, resname and residue_number columns"
        )
    insertion = decode_column(form, field_dim, "insertion_code")
    labels = []
    for i in range(len(number)):
        suffix = ""
        if insertion is not None:
            code = str(insertion[i]).strip()
            if code not in ("", "_"):
                suffix = code
        labels.append(
            f"{_clean(chain[i])}:{_clean(resname[i])}:{_clean(number[i])}{suffix}"
        )
    return np.array(labels, dtype=object)


def heavy_atom_mask(form: Form, field_dim: str) -> np.ndarray:
    """Mask non-hydrogen atoms when element or atom name columns exist."""
    element = decode_column(form, field_dim, "element")
    if element is not None:
        return np.array(
            [str(value).strip().upper() not in ("H", "D", "") for value in element],
            dtype=bool,
        )
    atom_name = decode_column(form, field_dim, "atom_name")
    if atom_name is not None:
        return np.array(
            [not str(value).strip().upper().startswith("H") for value in atom_name],
            dtype=bool,
        )
    return np.ones(np.asarray(form.data).shape[0], dtype=bool)


def split_chains(text: str) -> list[str]:
    """Parse a comma/space separated chain list."""
    if text is None:
        return []
    return [part for part in str(text).replace(",", " ").split() if part]


def residue_order(labels: np.ndarray) -> list[str]:
    seen: dict[str, None] = {}
    for label in labels:
        seen.setdefault(str(label), None)
    return list(seen)


def contact_stats(
    query: np.ndarray, reference: np.ndarray, cutoff: float
) -> tuple[np.ndarray, np.ndarray]:
    """Count reference points within ``cutoff`` and report the nearest distance."""
    from scipy.spatial import cKDTree

    tree = cKDTree(reference)
    counts = tree.query_ball_point(query, r=cutoff, return_length=True)
    distances, _ = tree.query(query, k=1)
    return np.asarray(counts, dtype=np.int64), np.asarray(distances, dtype=np.float64)
