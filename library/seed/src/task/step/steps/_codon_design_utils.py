"""Helpers for codon optimisation and DNA design quality control."""
from __future__ import annotations

import math

import numpy as np

from src.core import StepError

BASES = "TCAG"
AMINO_ACIDS = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODON_TABLE = {}
for index, codon in enumerate(
    a + b + c for a in BASES for b in BASES for c in BASES
):
    CODON_TABLE[codon] = AMINO_ACIDS[index]

AA_CODONS = {}
for codon, amino_acid in CODON_TABLE.items():
    AA_CODONS.setdefault(amino_acid, []).append(codon)
for amino_acid in AA_CODONS:
    AA_CODONS[amino_acid].sort()

STOP_CODONS = {"TAA", "TAG", "TGA"}
COMPLEMENT = str.maketrans("ACGT", "TGCA")


def translate(dna):
    dna = dna.upper()
    protein = []
    for start in range(0, len(dna) - 2, 3):
        codon = dna[start:start + 3]
        protein.append(CODON_TABLE.get(codon, "X"))
    return "".join(protein)


def reverse_complement(sequence):
    return sequence.translate(COMPLEMENT)[::-1]


def clean_protein(sequence, operator):
    cleaned = sequence.upper().replace("*", "").strip()
    if not cleaned or any(residue not in AA_CODONS or residue == "*" for residue in cleaned):
        raise StepError(
            f"{operator}: protein contains residues outside the standard genetic code"
        )
    return cleaned


def read_reference_cds(path, operator="codon_optimize"):
    counts = {amino_acid: {codon: 0 for codon in codons} for amino_acid, codons in AA_CODONS.items()}
    sequences = []
    name = None
    chunks = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name is not None:
                    sequences.append((name, "".join(chunks)))
                name = line[1:].split()[0] if line[1:].split() else "sequence"
                chunks = []
            else:
                chunks.append(line.upper())
    if name is not None:
        sequences.append((name, "".join(chunks)))
    if not sequences:
        raise StepError(f"{operator}: reference CDS FASTA is empty")
    used = 0
    for _, sequence in sequences:
        if len(sequence) < 30 or len(sequence) % 3 != 0:
            continue
        if any(base not in "ACGT" for base in sequence):
            continue
        protein = translate(sequence)
        if "*" in protein[:-1] or len(protein) < 10:
            continue
        if protein[-1] == "*":
            protein = protein[:-1]
        if "*" in protein:
            continue
        for offset, amino_acid in enumerate(protein):
            codon = sequence[offset * 3:offset * 3 + 3]
            if codon in counts.get(amino_acid, {}):
                counts[amino_acid][codon] += 1
        used += 1
    if used < 10:
        raise StepError(f"{operator}: fewer than 10 usable reference CDS sequences")
    weights = {}
    for amino_acid, table in counts.items():
        total = sum(table.values())
        maximum = max(table.values()) if table else 0
        for codon, count in table.items():
            if maximum == 0 or total == 0:
                weights[codon] = 0.5
            else:
                weights[codon] = max(count / maximum, 1e-6)
    return weights, used


def forbidden_hits(sequence, motifs):
    sequence = sequence.upper()
    hits = 0
    for motif in motifs:
        motif = motif.upper()
        if not motif:
            continue
        start = sequence.find(motif)
        while start != -1:
            hits += 1
            start = sequence.find(motif, start + 1)
        reverse = reverse_complement(motif)
        if reverse != motif:
            start = sequence.find(reverse)
            while start != -1:
                hits += 1
                start = sequence.find(reverse, start + 1)
    return hits


def max_homopolymer(sequence):
    best = 0
    run = 1
    for index in range(1, len(sequence)):
        if sequence[index] == sequence[index - 1]:
            run += 1
            best = max(best, run)
        else:
            run = 1
    return max(best, 1 if sequence else 0)


def gc_fraction(sequence):
    if not sequence:
        return 0.0
    return sum(1 for base in sequence if base in "GC") / len(sequence)


def cai_value(sequence, weights):
    dna = sequence.upper()
    logs = []
    for start in range(0, len(dna) - 2, 3):
        codon = dna[start:start + 3]
        amino_acid = CODON_TABLE.get(codon)
        if amino_acid in (None, "*", "M", "W"):
            continue
        weight = weights.get(codon)
        if weight is None:
            raise StepError("codon_design_qc: codon is absent from the reference table")
        logs.append(math.log(weight))
    return math.exp(sum(logs) / len(logs)) if logs else 0.0


def _codon_allowed(prefix, codon, motifs, max_run):
    candidate = prefix + codon
    for motif in motifs:
        if motif and motif in candidate[-len(motif) - 3:]:
            return False
        reverse = reverse_complement(motif) if motif else ""
        if reverse and reverse in candidate[-len(reverse) - 3:]:
            return False
    if max_run:
        suffix = candidate[-max_run:]
        if len(suffix) == max_run and len(set(suffix)) == 1:
            return False
    return True


def homopolymer_excess(sequence, max_run=6):
    excess = 0
    run = 0
    previous = ""
    for base in sequence:
        if base == previous:
            run += 1
        else:
            previous = base
            run = 1
        if run > max_run:
            excess += 1
    return excess


def repair_homopolymer(sequence, weights, motifs=(), max_run=6, rounds=200):
    dna = list(sequence.upper())
    length = len(dna)
    for _ in range(rounds):
        text = "".join(dna)
        if max_homopolymer(text) <= max_run:
            break
        base_hits = forbidden_hits(text, motifs)
        base_excess = homopolymer_excess(text, max_run)
        best = None
        for index in range(0, length - 2, 3):
            codon = "".join(dna[index:index + 3])
            amino_acid = CODON_TABLE.get(codon)
            if amino_acid in (None, "*", "M", "W"):
                continue
            for alternative in AA_CODONS[amino_acid]:
                if alternative == codon:
                    continue
                candidate = "".join(dna[:index]) + alternative + "".join(dna[index + 3:])
                excess = homopolymer_excess(candidate, max_run)
                if excess >= base_excess:
                    continue
                new_hits = forbidden_hits(candidate, motifs)
                if new_hits > base_hits:
                    continue
                loss = weights.get(codon, 0.0) - weights.get(alternative, 0.0)
                score = (excess, new_hits, round(loss, 6), alternative)
                if best is None or score < best[0]:
                    best = (score, index, alternative)
        if best is None:
            break
        _, index, alternative = best
        dna[index:index + 3] = list(alternative)
    return "".join(dna)


def repair_motifs(sequence, weights, motifs=(), max_run=6, rounds=200):
    dna = list(sequence.upper())
    length = len(dna)
    for _ in range(rounds):
        text = "".join(dna)
        base_hits = forbidden_hits(text, motifs)
        if not base_hits:
            break
        base_excess = homopolymer_excess(text, max_run)
        best = None
        for index in range(0, length - 2, 3):
            codon = "".join(dna[index:index + 3])
            amino_acid = CODON_TABLE.get(codon)
            if amino_acid in (None, "*", "M", "W"):
                continue
            for alternative in AA_CODONS[amino_acid]:
                if alternative == codon:
                    continue
                candidate = "".join(dna[:index]) + alternative + "".join(dna[index + 3:])
                hits = forbidden_hits(candidate, motifs)
                if hits >= base_hits:
                    continue
                excess = homopolymer_excess(candidate, max_run)
                if excess > base_excess:
                    continue
                loss = weights.get(codon, 0.0) - weights.get(alternative, 0.0)
                score = (hits, excess, round(loss, 6), alternative)
                if best is None or score < best[0]:
                    best = (score, index, alternative)
        if best is None:
            break
        _, index, alternative = best
        dna[index:index + 3] = list(alternative)
    return "".join(dna)


def optimize(protein, weights, motifs=(), gc_bounds=(0.3, 0.7), max_run=6):
    protein = clean_protein(protein, "codon_optimize")
    low, high = gc_bounds
    dna = []
    prefix = ""
    for amino_acid in protein:
        codons = AA_CODONS[amino_acid]
        ordered = sorted(codons, key=lambda codon: (-weights.get(codon, 0.0), codon))
        chosen = None
        for codon in ordered:
            if _codon_allowed(prefix, codon, motifs, max_run):
                chosen = codon
                break
        if chosen is None:
            chosen = min(
                ordered,
                key=lambda codon: (
                    max_homopolymer(prefix + codon),
                    forbidden_hits(prefix + codon, motifs),
                ),
            )
        dna.append(chosen)
        prefix = "".join(dna)[-12:]
    sequence = "".join(dna)
    sequence = harmonize(sequence, weights, (low + high) / 2.0, motifs, max_run)
    for _ in range(3):
        sequence = repair_motifs(sequence, weights, motifs, max_run)
        sequence = repair_homopolymer(sequence, weights, motifs, max_run)
    return sequence


def harmonize(sequence, weights, target_gc, motifs=(), max_run=6, rounds=200):
    dna = list(sequence.upper())
    length = len(dna)
    if length == 0:
        return ""
    for _ in range(rounds):
        current = gc_fraction("".join(dna))
        if abs(current - target_gc) < 0.005:
            break
        want_gc = current < target_gc
        best = None
        for index in range(0, length - 2, 3):
            codon = "".join(dna[index:index + 3])
            amino_acid = CODON_TABLE.get(codon)
            if amino_acid in (None, "*", "M", "W"):
                continue
            for alternative in AA_CODONS[amino_acid]:
                if alternative == codon:
                    continue
                alt_gc = sum(1 for base in alternative if base in "GC")
                cur_gc = sum(1 for base in codon if base in "GC")
                if want_gc and alt_gc <= cur_gc:
                    continue
                if not want_gc and alt_gc >= cur_gc:
                    continue
                candidate = "".join(dna[:index]) + alternative + "".join(dna[index + 3:])
                if forbidden_hits(candidate, motifs):
                    continue
                limit = max(max_run, max_homopolymer("".join(dna)))
                if max_run and max_homopolymer(candidate) > limit:
                    continue
                loss = weights.get(codon, 0.0) - weights.get(alternative, 0.0)
                gain = abs(alt_gc - cur_gc)
                score = (round(loss, 6), -gain, alternative)
                if best is None or score < best[0]:
                    best = (score, index, alternative)
        if best is None:
            break
        _, index, alternative = best
        dna[index:index + 3] = list(alternative)
    return "".join(dna)


def design_metrics(sequence, weights, motifs=()):
    dna = sequence.upper()
    protein = translate(dna)
    return {
        "length_bp": len(dna),
        "n_codons": len(dna) // 3,
        "gc_fraction": gc_fraction(dna),
        "cai": cai_value(dna, weights) if len(dna) % 3 == 0 else 0.0,
        "max_homopolymer": max_homopolymer(dna),
        "forbidden_sites": forbidden_hits(dna, motifs),
        "ends_with_stop": dna[-3:] in STOP_CODONS,
        "internal_stop": "*" in protein[:-1],
    }


def parse_motifs(text):
    motifs = []
    for item in str(text).replace(";", ",").split(","):
        item = item.strip().upper()
        if not item:
            continue
        if any(base not in "ACGT" for base in item):
            raise StepError("codon_optimize: motifs must contain only A, C, G and T")
        motifs.append(item)
    return motifs
