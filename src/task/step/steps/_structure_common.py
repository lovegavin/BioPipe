"""Shared helpers for structure-based operators."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError

from ._protein_common import (
    column_index,
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
    split_chains,
)


def field_columns(form, field_dim: str, names) -> None:
    """Raise a StepError naming the operator-agnostic missing column."""

    for column in names:
        if not has_column(form, field_dim, column):
            raise StepError(f"the PDB form has no '{column}' column")


def atom_coords(form, field_dim: str) -> np.ndarray:
    return np.column_stack(
        [
            np.asarray(form.data[:, column_index(form, field_dim, column)], dtype=np.float64)
            for column in ("x", "y", "z")
        ]
    )


def atom_names(form, field_dim: str) -> np.ndarray:
    return np.asarray(
        [str(value).strip() for value in decode_column(form, field_dim, "atom_name")],
        dtype=object,
    )


def residue_numbers(form, field_dim: str) -> np.ndarray:
    raw = np.asarray(
        [float(value) for value in decode_column(form, field_dim, "residue_number")],
        dtype=np.float64,
    )
    return np.rint(raw).astype(np.int64)


def insertion_codes(form, field_dim: str) -> np.ndarray:
    if not has_column(form, field_dim, "insertion_code"):
        return np.full(len(form.data), "", dtype=object)
    values = [
        str(value).strip() for value in decode_column(form, field_dim, "insertion_code")
    ]
    return np.asarray(["" if value == "_" else value for value in values], dtype=object)


def atom_keys(form, field_dim: str, names: np.ndarray) -> list[tuple[str, int, str, str]]:
    chain = [str(value).strip() for value in decode_column(form, field_dim, "chain")]
    numbers = residue_numbers(form, field_dim)
    codes = insertion_codes(form, field_dim)
    return [
        (chain[index], int(numbers[index]), str(codes[index]), str(names[index]))
        for index in range(len(chain))
    ]


def pick_chain_sides(
    present: set[str],
    binder_text,
    target_text,
    operator: str,
) -> tuple[list[str], list[str]]:
    """Select binder and target chains, deriving the empty side when possible."""

    present = set(present)
    binder = split_chains(binder_text)
    target = split_chains(target_text)
    if not binder and not target:
        raise StepError(
            f"{operator}: binder_chains or target_chains must select at "
            f"least one chain (available chains: {sorted(present)})"
        )
    if not binder:
        binder = sorted(present - set(target))
    if not target:
        target = sorted(present - set(binder))
    missing = sorted((set(binder) | set(target)) - present)
    if missing:
        raise StepError(
            f"{operator}: chain(s) " + ", ".join(missing) + " not found in the PDB form "
            f"(available chains: {sorted(present)})"
        )
    shared = sorted(set(binder) & set(target))
    if shared:
        raise StepError(
            f"{operator}: chain(s) " + ", ".join(shared) + " cannot be both binder and target"
        )
    if not binder or not target:
        raise StepError(
            f"{operator}: two chain groups are required; the structure "
            f"only provides {sorted(present)}"
        )
    return binder, target
