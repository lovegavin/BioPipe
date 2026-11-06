"""Shared helpers for structure validation operators.

The helpers work on the operator-agnostic PDB Form produced by ``PdbReader``
(``dims=[atom, field]``) and group atoms into polymer residues.  A residue is
treated as a polymer residue when a ``CA`` atom is present, which keeps waters
and ligands out of the missing-residue and peptide-bond analyses.
"""

from __future__ import annotations

import numpy as np

from src.core import StepError

from ._protein_common import (
    column_index,
    decode_column,
    has_column,
    heavy_atom_mask,
)
from ._structure_common import (
    atom_coords,
    atom_names,
    field_columns,
    insertion_codes,
    residue_numbers,
)

_BLANK_ALT = ("", "_", " ")


def altloc_column(form, field_dim: str) -> np.ndarray:
    """Decoded altloc identifiers, using ``_`` for a blank conformer."""
    n_atoms = len(form.data)
    if not has_column(form, field_dim, "altloc"):
        return np.full(n_atoms, "_", dtype=object)
    values = decode_column(form, field_dim, "altloc")
    return np.asarray(
        ["_" if str(value).strip() in _BLANK_ALT else str(value).strip() for value in values],
        dtype=object,
    )


def occupancy_column(form, field_dim: str) -> np.ndarray:
    """Occupancies as floats (NaN when the column is absent)."""
    index = column_index(form, field_dim, "occupancy")
    if index < 0:
        return np.full(len(form.data), np.nan)
    return np.asarray(form.data[:, index], dtype=np.float64)


def _prefer(new_alt: str, new_occ: float, old_alt: str, old_occ: float) -> bool:
    """Prefer the blank conformer, then the one with the higher occupancy."""
    new_blank = new_alt == "_"
    old_blank = old_alt == "_"
    if new_blank != old_blank:
        return new_blank
    if np.isfinite(new_occ) and np.isfinite(old_occ) and new_occ != old_occ:
        return new_occ > old_occ
    return False


def polymer_residues(form, atom_dim: str, field_dim: str) -> list[dict]:
    """Group heavy atoms into residues that carry a ``CA`` atom.

    Returns entries in file order with ``chain``, ``number``, ``icode``,
    ``label`` and per-atom ``coords``/``altloc``/``occupancy`` dictionaries.
    When several conformers exist, the blank one (or the highest occupancy)
    represents the residue.
    """
    field_columns(form, field_dim, ("chain", "residue_number", "atom_name"))
    chains = decode_column(form, field_dim, "chain")
    numbers = residue_numbers(form, field_dim)
    codes = insertion_codes(form, field_dim)
    names = atom_names(form, field_dim)
    coords = atom_coords(form, field_dim)
    altlocs = altloc_column(form, field_dim)
    occupancy = occupancy_column(form, field_dim)
    mask = heavy_atom_mask(form, field_dim)

    entries: dict[tuple[str, int, str], dict] = {}
    order: list[tuple[str, int, str]] = []
    for index in range(len(names)):
        if not mask[index]:
            continue
        chain = str(chains[index]).strip() or "_"
        key = (chain, int(numbers[index]), str(codes[index]))
        entry = entries.get(key)
        if entry is None:
            suffix = "" if not key[2] or key[2] == "_" else key[2]
            entry = {
                "chain": chain,
                "number": key[1],
                "icode": "" if key[2] == "_" else key[2],
                "label": f"{chain}:{key[1]}{suffix}",
                "coords": {},
                "altloc": {},
                "occupancy": {},
            }
            entries[key] = entry
            order.append(key)
        name = str(names[index]).strip().upper()
        old_alt = entry["altloc"].get(name)
        if old_alt is None or _prefer(
            str(altlocs[index]), float(occupancy[index]), old_alt, entry["occupancy"][name]
        ):
            entry["coords"][name] = coords[index]
            entry["altloc"][name] = str(altlocs[index])
            entry["occupancy"][name] = float(occupancy[index])
    return [entries[key] for key in order if "CA" in entries[key]["coords"]]


def chain_sequences(residues: list[dict]) -> dict[str, list[dict]]:
    """Group residues by chain and sort them by residue number."""
    grouped: dict[str, list[dict]] = {}
    for entry in residues:
        grouped.setdefault(entry["chain"], []).append(entry)
    for chain in grouped:
        grouped[chain].sort(key=lambda entry: (entry["number"], entry["icode"]))
    return {chain: grouped[chain] for chain in sorted(grouped)}


def clean_residues(residues: list[dict], chain: str, operator: str) -> list[dict]:
    """Optionally restrict residues to one chain, raising when it is absent."""
    if not residues:
        raise StepError(f"{operator}: no polymer residues with a CA atom were found")
    if not chain:
        return residues
    selected = [entry for entry in residues if entry["chain"] == chain]
    if not selected:
        available = sorted({entry["chain"] for entry in residues})
        raise StepError(
            f"{operator}: chain '{chain}' not found (available: {', '.join(available)})"
        )
    return selected
