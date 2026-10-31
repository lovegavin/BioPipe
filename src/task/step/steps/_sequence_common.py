"""Small shared helpers for sequence-oriented operators.

The helpers deliberately keep the sequence-code representation used by the
FASTA reader: rows are sequences, columns positions, missing positions are
NaN and ``info["alphabet_map"]`` maps characters to integer codes.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError

DNA_CHARS = ("A", "C", "G", "T", "N")
RNA_CHARS = ("A", "C", "G", "U", "N")
PROTEIN_CHARS = tuple("ACDEFGHIKLMNPQRSTVWY*")

DNA_MAP = {ch: i for i, ch in enumerate(DNA_CHARS)}
RNA_MAP = {ch: i for i, ch in enumerate(RNA_CHARS)}
PROTEIN_MAP = {ch: i for i, ch in enumerate(PROTEIN_CHARS)}
UNKNOWN_CODE = 5

CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_COMPLEMENT_DNA = str.maketrans("ACGTNacgtn", "TGCANtgcan")
_COMPLEMENT_RNA = str.maketrans("ACGUNacgun", "UGCANugcan")


def decode_sequences(form: Form, sequence_dim: str, position_dim: str) -> list[str]:
    """Decode a sequence-codes Form into uppercase strings."""
    if form.data.ndim != 2:
        raise StepError(f"sequence input must be 2D, got ndim={form.data.ndim}")
    if form.dims[0] != sequence_dim or form.dims[1] != position_dim:
        raise StepError(
            f"sequence input expected [{sequence_dim}, {position_dim}], got {form.dims}"
        )
    if form.info.get("representation") != "sequence_codes":
        raise StepError("sequence input is not a sequence_codes Form")
    alphabet_map = form.info.get("alphabet_map")
    if not isinstance(alphabet_map, dict):
        raise StepError("sequence input has no info.alphabet_map")
    code_to_char: dict[int, str] = {}
    for ch, code in alphabet_map.items():
        code_to_char.setdefault(int(code), str(ch).upper())
    unknown = int(form.info.get("unknown_code", UNKNOWN_CODE))
    out: list[str] = []
    for row in np.asarray(form.data):
        chars = []
        for value in row:
            if not np.isfinite(value):
                break
            code = int(value)
            if code == unknown:
                chars.append("N")
            else:
                chars.append(code_to_char.get(code, "N"))
        out.append("".join(chars))
    return out


def encode_sequences(
    sequences: list[str],
    sequence_dim: str,
    position_dim: str,
    alphabet: str,
    alphabet_map: dict[str, int] | None = None,
    labels: dict | None = None,
    info_extra: dict | None = None,
) -> Form:
    """Encode sequences, padding shorter rows with NaN."""
    if alphabet == "protein":
        amap = dict(PROTEIN_MAP)
    elif alphabet == "rna":
        amap = dict(RNA_MAP)
    else:
        amap = dict(DNA_MAP)
    if alphabet_map:
        amap.update({str(k).upper(): int(v) for k, v in alphabet_map.items()})
    unknown = max(amap.values()) + 1 if amap else 0
    max_len = max((len(s) for s in sequences), default=0)
    data = np.full((len(sequences), max_len), np.nan, dtype=np.float32)
    for i, seq in enumerate(sequences):
        for j, ch in enumerate(seq.upper()):
            data[i, j] = amap.get(ch, unknown)
    if not labels:
        labels = {
            sequence_dim: {f"seq{i + 1}": i for i in range(len(sequences))},
            position_dim: {str(i): i for i in range(max_len)},
        }
    info = {
        "missing_code": np.nan,
        "representation": "sequence_codes",
        "alphabet": alphabet,
        "alphabet_map": amap,
        "unknown_code": unknown,
    }
    if info_extra:
        info.update(info_extra)
    form = Form(data=data, dims=[sequence_dim, position_dim], labels=labels, info=info)
    form.validate()
    return form


def reverse_complement(sequence: str, alphabet: str) -> str:
    table = _COMPLEMENT_RNA if alphabet == "rna" else _COMPLEMENT_DNA
    comp = sequence.translate(table)
    return comp[::-1]


def translate_sequence(sequence: str, frame: int = 0, to_stop: bool = False) -> str:
    seq = sequence.upper().replace("U", "T")
    if frame not in (0, 1, 2):
        raise StepError(f"frame must be 0, 1 or 2, got {frame}")
    aa: list[str] = []
    for i in range(frame, len(seq) - 2, 3):
        codon = seq[i:i + 3]
        residue = CODON_TABLE.get(codon, "X")
        if residue == "*" and to_stop:
            break
        aa.append(residue)
    return "".join(aa)


def count_motif(seq: str, motif: str) -> int:
    motif = motif.upper()
    if not motif:
        return 0
    return sum(1 for i in range(len(seq) - len(motif) + 1) if seq[i:i + len(motif)] == motif)


def positions(n: int, dim: str, prefix: str = "") -> dict[str, int]:
    return {f"{prefix}{i}": i for i in range(n)}
