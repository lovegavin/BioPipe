"""Codon usage bias helpers (CAI, ENC, GC3s, RSCU)."""
from __future__ import annotations

import math

BASES = "TCAG"
AA_CODON_ORDER = {
    "F": ["TTT", "TTC"], "L": ["TTA", "TTG", "CTT", "CTC", "CTA", "CTG"],
    "I": ["ATT", "ATC", "ATA"], "M": ["ATG"], "V": ["GTT", "GTC", "GTA", "GTG"],
    "S": ["TCT", "TCC", "TCA", "TCG", "AGT", "AGC"], "P": ["CCT", "CCC", "CCA", "CCG"],
    "T": ["ACT", "ACC", "ACA", "ACG"], "A": ["GCT", "GCC", "GCA", "GCG"],
    "Y": ["TAT", "TAC"], "H": ["CAT", "CAC"], "Q": ["CAA", "CAG"], "N": ["AAT", "AAC"],
    "K": ["AAA", "AAG"], "D": ["GAT", "GAC"], "E": ["GAA", "GAG"],
    "C": ["TGT", "TGC"], "W": ["TGG"], "R": ["CGT", "CGC", "CGA", "CGG", "AGA", "AGG"],
    "G": ["GGT", "GGC", "GGA", "GGG"],
}
CODON_TABLE = {c: aa for aa, codons in AA_CODON_ORDER.items() for c in codons}
STOP_CODONS = {"TAA", "TAG", "TGA"}
CODONS = sorted(CODON_TABLE)

def clean_cds(sequence, operator):
    seq = str(sequence).upper().replace("U", "T")
    if len(seq) < 6 or len(seq) % 3:
        raise ValueError(f"{operator}: sequence length must be a multiple of three")
    while len(seq) >= 3 and seq[-3:] in STOP_CODONS:
        seq = seq[:-3]
    if not seq or any(base not in "ACGT" for base in seq):
        raise ValueError(f"{operator}: sequence contains non-ACGT bases")
    return seq

def codon_counts(sequence):
    counts = {}
    for index in range(0, len(sequence), 3):
        codon = sequence[index:index + 3]
        if len(codon) == 3 and codon in CODON_TABLE:
            counts[codon] = counts.get(codon, 0) + 1
    return counts

def enc_wright(sequence):
    counts = codon_counts(sequence)
    if not counts:
        return float("nan")
    means = {}
    for size, weight in ((2, 9.0), (3, 1.0), (4, 5.0), (6, 3.0)):
        families = [aa for aa, codons in AA_CODON_ORDER.items() if len(codons) == size]
        f_values = []
        for aa in families:
            codons = AA_CODON_ORDER[aa]
            n = sum(counts.get(codon, 0) for codon in codons)
            if n <= 1:
                continue
            squares = sum((counts.get(codon, 0) / n) ** 2 for codon in codons)
            f_value = (n * squares - 1.0) / (n - 1.0)
            if f_value > 1e-7:
                f_values.append(f_value)
        means[size] = sum(f_values) / len(f_values) if f_values else None
    enc_value = 2.0
    for size, weight in ((2, 9.0), (3, 1.0), (4, 5.0), (6, 3.0)):
        average = means[size]
        if average is None and size == 3 and means[2] is not None and means[4] is not None:
            average = 0.5 * (means[2] + means[4])
        if average is None or average <= 0:
            return float("nan")
        enc_value += weight / average
    return min(enc_value, 61.0)


def gc3s_variants(sequence):
    counts = codon_counts(sequence)
    out = {}
    positions = [codon[2] for codon in counts for _ in range(counts[codon])]
    out["all"] = (positions.count("G") + positions.count("C")) / len(positions) if positions else 0.0
    syn = [codon[2] for codon in counts for _ in range(counts[codon])
           if len(AA_CODON_ORDER[CODON_TABLE[codon]]) > 1]
    out["multi"] = (syn.count("G") + syn.count("C")) / len(syn) if syn else 0.0
    four = [codon[2] for codon in counts for _ in range(counts[codon])
            if len(AA_CODON_ORDER[CODON_TABLE[codon]]) in (2, 4)]
    out["2_4fold"] = (four.count("G") + four.count("C")) / len(four) if four else 0.0
    return out

def rscu(counts):
    values = {}
    for aa, codons in AA_CODON_ORDER.items():
        total = sum(counts.get(codon, 0) for codon in codons)
        for codon in codons:
            values[codon] = (counts.get(codon, 0) * len(codons) / total) if total else 0.0
    return values
