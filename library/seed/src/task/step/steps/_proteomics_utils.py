"""Peptide chemistry helpers shared by the proteomics operators."""
from __future__ import annotations

from src.core import StepError

# Monoisotopic residue masses (Da) from the pyteomics/Unimod consensus,
# including selenocysteine (U) and pyrrolysine (O).
_RESIDUE_MASS = {
    "A": 71.03711378471,
    "R": 156.1011110236,
    "N": 114.04292744114,
    "D": 115.02694302383,
    "C": 103.00918478471,
    "E": 129.04259308797,
    "Q": 128.05857750528,
    "G": 57.02146372057,
    "H": 137.05891185845,
    "I": 113.08406397713,
    "L": 113.08406397713,
    "K": 128.094963014,
    "M": 131.04048491299,
    "F": 147.06841391299,
    "P": 97.05276384885,
    "S": 87.03202840427,
    "T": 101.04767846841,
    "W": 186.07931294986,
    "Y": 163.06332853255,
    "V": 99.06841391299,
    "U": 150.95363508471,
    "O": 237.14772686285,
}
_WATER = 18.0105646837
_PROTON = 1.007276466621

_ENZYMES = {
    "trypsin": ("KR", "P"),
    "lys-c": ("K", "P"),
    "arg-c": ("R", "P"),
}


def enzyme_rule(enzyme):
    """Return the (cleaved residues, residues that block cleavage) pair."""
    key = str(enzyme).lower()
    if key not in _ENZYMES:
        raise StepError(f"unsupported enzyme {enzyme!r}")
    return _ENZYMES[key]


def cleavage_sites(sequence, enzyme):
    """Return zero-based positions after which the enzyme cleaves."""
    residues, avoid = enzyme_rule(enzyme)
    seq = str(sequence).upper()
    return [
        index
        for index in range(len(seq) - 1)
        if seq[index] in residues and seq[index + 1] not in avoid
    ]


def digest_peptides(sequence, enzyme="trypsin", missed_cleavages=0):
    """Return ``(start, end, missed)`` zero-based half-open peptide spans."""
    if missed_cleavages < 0:
        raise StepError("missed_cleavages must be >= 0")
    seq = str(sequence).upper()
    if not seq:
        return []
    bounds = [0] + [cut + 1 for cut in cleavage_sites(seq, enzyme)] + [len(seq)]
    starts, ends = bounds[:-1], bounds[1:]
    spans = []
    for index in range(len(starts)):
        for extra in range(missed_cleavages + 1):
            target = index + extra
            if target >= len(starts):
                break
            spans.append((starts[index], ends[target], extra))
    return spans


def peptide_mass(sequence, protein="", position=0):
    """Monoisotopic mass of a peptide (residue sum plus one water)."""
    total = _WATER
    for residue in str(sequence).upper():
        mass = _RESIDUE_MASS.get(residue)
        if mass is None:
            raise StepError(
                f"unsupported residue {residue!r} in "
                f"{protein or 'peptide'} at position {position}"
            )
        total += mass
    return total


def peptide_mz(mass, charge):
    """Monoisotopic m/z for a singly protonated ion of the given charge."""
    charge = int(charge)
    if charge < 1:
        raise StepError("charge must be >= 1")
    return (float(mass) + charge * _PROTON) / charge
