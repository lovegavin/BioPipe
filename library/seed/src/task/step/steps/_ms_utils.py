"""Mass-spectrometry helpers: residue formulas, fragment ions and isotope envelopes."""

from __future__ import annotations

import math
from itertools import product

from biopipe_sdk import StepError

PROTON = 1.007276466621
WATER = 18.01056468403

ELEMENT_MASS = {
    "C": 12.0,
    "H": 1.00782503223,
    "N": 14.00307400443,
    "O": 15.99491461957,
    "S": 31.9720711744,
}

HEAVY_SHIFT = {
    "C": 1.00335483507,
    "H": 1.006276746,
    "N": 0.9970348935,
    "O": 2.0042449923,
    "S": 1.9957959,
}

HEAVY_ABUNDANCE = {
    "C": 0.0107,
    "H": 0.000115,
    "N": 0.00364,
    "O": 0.00205,
    "S": 0.0425,
}

AA_FORMULA = {
    "A": {"C": 3, "H": 5, "N": 1, "O": 1},
    "R": {"C": 6, "H": 12, "N": 4, "O": 1},
    "N": {"C": 4, "H": 6, "N": 2, "O": 2},
    "D": {"C": 4, "H": 5, "N": 1, "O": 3},
    "C": {"C": 3, "H": 5, "N": 1, "O": 1, "S": 1},
    "E": {"C": 5, "H": 7, "N": 1, "O": 3},
    "Q": {"C": 5, "H": 8, "N": 2, "O": 2},
    "G": {"C": 2, "H": 3, "N": 1, "O": 1},
    "H": {"C": 6, "H": 7, "N": 3, "O": 1},
    "I": {"C": 6, "H": 11, "N": 1, "O": 1},
    "L": {"C": 6, "H": 11, "N": 1, "O": 1},
    "K": {"C": 6, "H": 12, "N": 2, "O": 1},
    "M": {"C": 5, "H": 9, "N": 1, "O": 1, "S": 1},
    "F": {"C": 9, "H": 9, "N": 1, "O": 1},
    "P": {"C": 5, "H": 7, "N": 1, "O": 1},
    "S": {"C": 3, "H": 5, "N": 1, "O": 2},
    "T": {"C": 4, "H": 7, "N": 1, "O": 2},
    "W": {"C": 11, "H": 10, "N": 2, "O": 1},
    "Y": {"C": 9, "H": 9, "N": 1, "O": 2},
    "V": {"C": 5, "H": 9, "N": 1, "O": 1},
}

RESIDUE_MASS = {}
for _aa, _formula in AA_FORMULA.items():
    RESIDUE_MASS[_aa] = sum(ELEMENT_MASS[e] * n for e, n in _formula.items())


def add_formula(target, formula, scale=1):
    for element, count in formula.items():
        target[element] = target.get(element, 0) + count * scale


def peptide_formula(sequence, operator):
    formula = {}
    for residue in sequence:
        if residue not in AA_FORMULA:
            raise ValueError(f"{operator}: unsupported residue {residue!r}")
        add_formula(formula, AA_FORMULA[residue])
    add_formula(formula, {"H": 2, "O": 1})
    return formula


def formula_mass(formula):
    return sum(ELEMENT_MASS[element] * count for element, count in formula.items())


def residue_mass(sequence, operator):
    total = WATER
    for residue in sequence:
        if residue not in RESIDUE_MASS:
            raise ValueError(f"{operator}: unsupported residue {residue!r}")
        total += RESIDUE_MASS[residue]
    return total


def fragment_ions(sequence, ion_types=("b", "y"), max_charge=2):
    prefix = [0.0]
    for residue in sequence:
        prefix.append(prefix[-1] + RESIDUE_MASS[residue])
    total = prefix[-1]
    rows = []
    length = len(sequence)
    for charge in range(1, max_charge + 1):
        for position in range(1, length):
            if "b" in ion_types:
                neutral = prefix[position]
                rows.append(
                    {
                        "type": "b",
                        "position": position,
                        "charge": charge,
                        "neutral": neutral,
                        "mz": (neutral + charge * PROTON) / charge,
                    }
                )
            if "y" in ion_types:
                neutral = total - prefix[length - position] + WATER
                rows.append(
                    {
                        "type": "y",
                        "position": position,
                        "charge": charge,
                        "neutral": neutral,
                        "mz": (neutral + charge * PROTON) / charge,
                    }
                )
    return rows


def _binomial(count, probability, limit):
    terms = []
    for k in range(0, min(count, limit) + 1):
        terms.append((k, math.comb(count, k) * probability**k * (1 - probability) ** (count - k)))
    return terms


def isotope_envelope(sequence, operator, max_peaks=4, charge=1):
    if max_peaks < 1:
        raise ValueError("peptide_isotope_envelope: max_peaks must be at least 1")
    if charge < 1:
        raise ValueError("peptide_isotope_envelope: charge must be at least 1")
    formula = peptide_formula(sequence, operator)
    mono = formula_mass(formula)
    elements = ["C", "H", "N", "O", "S"]
    limits = {"C": 8, "H": 6, "N": 6, "O": 5, "S": 4}
    terms = []
    for element in elements:
        count = formula.get(element, 0)
        if count <= 0:
            terms.append([(0, 1.0)] if element == "C" else [(0, 1.0)])
            continue
        terms.append(_binomial(count, HEAVY_ABUNDANCE[element], limits[element]))
    peaks = []
    for combination in product(*terms):
        shift = 0.0
        probability = 1.0
        for element, (heavy, term_probability) in zip(elements, combination):
            shift += HEAVY_SHIFT[element] * heavy
            probability *= term_probability
        if probability < 1e-12:
            continue
        peaks.append((shift, probability))
    peaks.sort()
    merged = []
    for shift, probability in peaks:
        if merged and shift - merged[-1][0] < 0.002:
            previous_shift, previous_probability = merged[-1]
            total = previous_probability + probability
            merged[-1] = (
                (previous_shift * previous_probability + shift * probability) / total,
                total,
            )
        else:
            merged.append((shift, probability))
    binned = {}
    for shift, probability in merged:
        nominal = int(round(shift))
        previous = binned.get(nominal)
        if previous:
            total = previous[1] + probability
            binned[nominal] = (
                (previous[0] * previous[1] + shift * probability) / total,
                total,
            )
        else:
            binned[nominal] = (shift, probability)
    selected = [binned[nominal] for nominal in sorted(binned)[:max_peaks]]
    denominator = max(probability for _, probability in selected) if selected else 1.0
    rows = []
    for shift, probability in selected:
        mz = (mono + shift + charge * PROTON) / charge
        rows.append(
            {
                "mz": mz,
                "fraction": probability,
                "intensity": 100.0 * probability / denominator,
                "shift": shift,
            }
        )
    return rows


def parse_mods(text, operator):
    mods = {}
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise StepError(f"{operator}: modifications must look like RESIDUE:MASS, got {chunk!r}")
        residue, mass = chunk.split(":", 1)
        residue = residue.strip().upper()
        if residue not in AA_FORMULA:
            raise StepError(f"{operator}: unknown residue {residue!r} in modifications")
        try:
            mods[residue] = float(mass)
        except ValueError as error:
            raise StepError(f"{operator}: invalid modification mass {mass!r}") from error
    return mods


def modified_mass(sequence, fixed_mods, operator):
    base = residue_mass(sequence, operator)
    shift = 0.0
    sites = 0
    for residue in sequence:
        if residue in fixed_mods:
            shift += fixed_mods[residue]
            sites += 1
    return base, base + shift, shift, sites
