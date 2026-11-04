"""Shared aromatic-ring and charged-group geometry for structure operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

RING_ATOMS: dict[str, tuple[tuple[str, ...], ...]] = {
    "PHE": (("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),),
    "TYR": (("CG", "CD1", "CD2", "CE1", "CE2", "CZ"),),
    "TRP": (
        ("CG", "CD1", "NE1", "CE2", "CD2"),
        ("CD2", "CE2", "CE3", "CZ2", "CZ3", "CH2"),
    ),
    "HIS": (("CG", "ND1", "CD2", "CE1", "NE2"),),
}
CATION_ATOMS: dict[str, tuple[str, ...]] = {
    "LYS": ("NZ",),
    "ARG": ("CZ", "NH1", "NH2"),
    "HIS": ("ND1", "NE2"),
}
_AMIDE_ATOMS = ("C", "O")
_AMIDE_N = "N"


def _plane(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Centroid and unit normal of a planar group of points."""
    centroid = points.mean(axis=0)
    centred = points - centroid
    _u, _s, vh = np.linalg.svd(centred, full_matrices=False)
    normal = vh[-1]
    length = float(np.linalg.norm(normal))
    if length < 1e-9:
        return centroid, np.zeros(3)
    return centroid, normal / length


def angle_between(first: np.ndarray, second: np.ndarray) -> float:
    """Unsigned angle in degrees between two vectors, 0..180."""
    a = float(np.linalg.norm(first))
    b = float(np.linalg.norm(second))
    if a < 1e-9 or b < 1e-9:
        return float("nan")
    cosine = float(np.clip(np.dot(first, second) / (a * b), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def ring_planes(
    coordinates: np.ndarray,
    resnames: np.ndarray,
    atom_names: np.ndarray,
    labels: np.ndarray,
) -> list[dict]:
    """Every aromatic ring with its centroid, normal and member atom labels."""
    by_residue: dict[str, dict[str, int]] = {}
    order: list[str] = []
    for index, label in enumerate(labels):
        label = str(label)
        if label not in by_residue:
            by_residue[label] = {}
            order.append(label)
        by_residue[label][str(atom_names[index])] = index
    rings: list[dict] = []
    for label in order:
        atoms = by_residue[label]
        resname = str(resnames[list(atoms.values())[0]])
        definitions = RING_ATOMS.get(resname)
        if definitions is None:
            continue
        for ring_index, names in enumerate(definitions):
            if not all(name in atoms for name in names):
                continue
            points = np.asarray(
                [coordinates[atoms[name]] for name in names], dtype=np.float64
            )
            centroid, normal = _plane(points)
            rings.append(
                {
                    "label": label,
                    "residue": label,
                    "resname": resname,
                    "ring_index": ring_index,
                    "centroid": centroid,
                    "normal": normal,
                    "atoms": names,
                    "atom_count": len(names),
                }
            )
    return rings


def cation_centroids(
    coordinates: np.ndarray,
    resnames: np.ndarray,
    atom_names: np.ndarray,
    labels: np.ndarray,
) -> list[dict]:
    """Charged cations (LYS NZ, ARG CZ/NH1/NH2, HIS ND1/NE2) per residue."""
    groups: dict[str, dict] = {}
    order: list[str] = []
    for index, label in enumerate(labels):
        label = str(label)
        resname = str(resnames[index])
        names = CATION_ATOMS.get(resname)
        if names is None or str(atom_names[index]) not in names:
            continue
        if label not in groups:
            groups[label] = {"label": label, "resname": resname, "points": []}
            order.append(label)
        groups[label]["points"].append(coordinates[index])
    cations: list[dict] = []
    for label in order:
        entry = groups[label]
        points = np.asarray(entry["points"], dtype=np.float64)
        cations.append(
            {
                "label": label,
                "residue": label,
                "resname": entry["resname"],
                "centroid": points.mean(axis=0),
                "atom_count": int(points.shape[0]),
            }
        )
    return cations


def amide_groups(
    coordinates: np.ndarray,
    resnames: np.ndarray,
    atom_names: np.ndarray,
    labels: np.ndarray,
    chains: np.ndarray,
    numbers: np.ndarray,
) -> list[dict]:
    """Amide planes built from residue C/O and the next residue's N."""
    atoms: dict[str, dict[str, np.ndarray]] = {}
    metadata: dict[str, tuple[str, str, int]] = {}
    for index, label in enumerate(labels):
        label = str(label)
        name = str(atom_names[index])
        if name in _AMIDE_ATOMS or name == _AMIDE_N:
            atoms.setdefault(label, {})[name] = coordinates[index]
            metadata.setdefault(
                label, (str(chains[index]), str(resnames[index]), int(numbers[index]))
            )
    by_chain: dict[str, list[str]] = {}
    for label, (chain, _resname, _number) in metadata.items():
        by_chain.setdefault(chain, []).append(label)
    groups: list[dict] = []
    for chain, chain_labels in by_chain.items():
        chain_labels.sort(key=lambda label: metadata[label][2])
        for first, second in zip(chain_labels, chain_labels[1:]):
            carbonyl = atoms.get(first, {})
            amide = atoms.get(second, {})
            if "C" not in carbonyl or "O" not in carbonyl or _AMIDE_N not in amide:
                continue
            carbon = carbonyl["C"]
            oxygen = carbonyl["O"]
            nitrogen = amide[_AMIDE_N]
            groups.append(
                {
                    "label": first,
                    "next": second,
                    "chain": chain,
                    "resname": metadata[first][1],
                    "carbon": carbon,
                    "carbonyl": oxygen - carbon,
                    "n_bond": nitrogen - carbon,
                    "midpoint": (carbon + oxygen) / 2.0,
                }
            )
    return groups


def require_form(form, atom_dim: str, field_dim: str, operator: str) -> None:
    """Validate the PDB-style input contract shared by these operators."""
    if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
        raise StepError(
            f"{operator}: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
            f"got {list(form.dims)}"
        )
