"""Restriction enzyme recognition sites and linear/circular digests."""
from __future__ import annotations

import re
import numpy as np

from src.core import StepError

# name: (recognition site, bases before the cut)
ENZYMES = {
    "EcoRI": ("GAATTC", 1),
    "BamHI": ("GGATCC", 1),
    "HindIII": ("AAGCTT", 1),
    "PstI": ("CTGCAG", 5),
    "SalI": ("GTCGAC", 1),
    "XhoI": ("CTCGAG", 1),
    "NotI": ("GCGGCCGC", 2),
    "XbaI": ("TCTAGA", 1),
    "KpnI": ("GGTACC", 5),
    "SmaI": ("CCCGGG", 3),
    "SacI": ("GAGCTC", 5),
    "SphI": ("GCATGC", 5),
    "NcoI": ("CCATGG", 1),
    "NdeI": ("CATATG", 2),
    "EcoRV": ("GATATC", 3),
    "BglII": ("AGATCT", 1),
    "ClaI": ("ATCGAT", 2),
    "MluI": ("ACGCGT", 1),
    "NheI": ("GCTAGC", 1),
    "SpeI": ("ACTAGT", 1),
    "ScaI": ("AGTACT", 3),
    "StuI": ("AGGCCT", 3),
    "PvuII": ("CAGCTG", 3),
    "DraI": ("TTTAAA", 3),
    "AatII": ("GACGTC", 5),
    "SnaBI": ("TACGTA", 3),
    "FspI": ("TGCGCA", 3),
    "AseI": ("ATTAAT", 2),
    "SspI": ("AATATT", 3),
}

_COMPLEMENT = str.maketrans("ACGTRYKMSWBDHVN", "TGCAYRMKSWVHDBN")
_CODES = {"A": "A", "C": "C", "G": "G", "T": "T", "N": "[ACGT]"}


def parse_enzymes(text):
    names = [item.strip() for item in str(text).split(",") if item.strip()]
    if not names:
        raise StepError("restriction_digest: at least one enzyme is required")
    unknown = [name for name in names if name not in ENZYMES]
    if unknown:
        raise StepError(f"restriction_digest: unsupported enzyme(s): {', '.join(unknown)}")
    return names


def _regex(site):
    return "".join(_CODES[base] for base in site)


def site_starts(sequence, site):
    """0-based start positions of a recognition site on either strand."""
    sequence = sequence.upper()
    starts = {match.start() for match in re.finditer(f"(?=({_regex(site)}))", sequence)}
    reverse = site.translate(_COMPLEMENT)[::-1]
    if reverse != site:
        starts |= {match.start() for match in re.finditer(f"(?=({_regex(reverse)}))", sequence)}
    return sorted(starts)


def cut_positions(sequence, enzymes, circular=False):
    """0-based cut indices: the position of the first base after the cut."""
    length = len(sequence)
    text = sequence.upper()
    if circular and length:
        text = text + text[: max(len(ENZYMES[name][0]) for name in enzymes) - 1]
    cuts = set()
    for name in enzymes:
        site, offset = ENZYMES[name]
        if offset < 0 or offset > len(site):
            raise StepError(f"restriction_digest: invalid offset for {name}")
        for start in site_starts(text, site):
            cuts.add((start + offset) % length)
    return sorted(cuts)


def digest(sequence, enzymes, circular):
    """Return (cuts, fragments); fragments are (start, length) in 0-based bases."""
    length = len(sequence)
    if length == 0:
        raise StepError("restriction_digest: the sequence is empty")
    cuts = cut_positions(sequence, enzymes, circular)
    if not cuts:
        return cuts, [(0, length)]
    if circular:
        fragments = []
        for index, start in enumerate(cuts):
            following = cuts[(index + 1) % len(cuts)]
            size = (following - start) % length
            fragments.append((start, size if size else length))
        return cuts, fragments
    fragments = []
    edges = [0] + cuts + [length]
    for index in range(len(edges) - 1):
        fragments.append((edges[index], edges[index + 1] - edges[index]))
    return cuts, fragments


def gc_fraction(sequence):
    sequence = sequence.upper()
    canonical = sum(1 for base in sequence if base in "ACGT")
    if canonical == 0:
        return float("nan")
    return (sequence.count("G") + sequence.count("C")) / canonical
