"""Shared SMILES parsing helpers for the RDKit operators.

RDKit is imported lazily inside the helpers so that the step modules stay
importable (and the registry stays scannable) without RDKit installed.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError


def parse_smiles_text(text: str, operator: str) -> list[tuple[str, str]]:
    """Parse ``SMILES [name]`` lines into (name, SMILES) pairs.

    Blank lines and ``#`` comments are skipped. Names are made unique so they
    can key the molecule axis of a Form.
    """
    rows: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        smiles = parts[0]
        base = parts[1] if len(parts) > 1 else f"mol{len(rows) + 1}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        name = base if count == 1 else f"{base}#{count}"
        rows.append((name, smiles))
    if not rows:
        raise StepError(
            f"{operator}: smiles must contain at least one SMILES line "
            "('SMILES [name]' per line)"
        )
    return rows


def build_molecules(text: str, operator: str):
    """Parse every SMILES line with RDKit, raising StepError on bad input."""
    from rdkit import Chem

    molecules = []
    for name, smiles in parse_smiles_text(text, operator):
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            raise StepError(
                f"{operator}: cannot parse SMILES '{smiles}' for molecule "
                f"'{name}'"
            )
        molecules.append((name, molecule))
    return molecules


def molecule_labels(names: list[str], dimension: str) -> dict[str, int]:
    """Return a Form label mapping for the molecule axis."""
    if len(names) != len(set(names)):
        raise StepError("rdkit: molecule names must be unique")
    return {name: position for position, name in enumerate(names)}


def float_matrix(values: list[list[float]]) -> np.ndarray:
    """Return a private float32 copy of a nested list."""
    return np.array(values, dtype=np.float32)
