# src/reader/readers/fasta_reader.py
"""FASTA reader.

Parses nucleotide or protein sequences.

Layout:
    axis 0 = sequence, axis 1 = position.

Sequences of different lengths are padded with NaN to the maximum
length found in the file. Characters are encoded as integers. For
nucleotide input the legacy code table is used:

    A=0, C=1, G=2, T=3, U=3, N=4, anything else=5

When the alphabet is ``protein`` the twenty standard residues plus
``*`` use the code table shared with the sequence operators
(``ACDEFGHIKLMNPQRSTVWY*`` -> 0..20) and every other residue
(``B``, ``X``, ``Z``, ``J``, ...) is stored as ``unknown_code`` 21
instead of the nucleotide code 5.

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           sequence: first token after '>'
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto`` for position and
``builtin`` for sequence. Duplicate identifiers are disambiguated by
appending ``#<position>``.

Sequence identifiers remain string axis labels; they are not data encoders.

The alphabet is inferred from the observed characters and recorded
in ``info["alphabet"]`` as one of ``"dna"``, ``"rna"`` or
``"protein"``. Pass ``alphabet`` (``auto``/``dna``/``rna``/``protein``)
to override the inference.

Reference
---------
FASTA format:
https://en.wikipedia.org/wiki/FASTA_format

Info fields set:

    missing_code      np.nan
    alphabet          "dna" | "rna" | "protein"
    alphabet_map      character -> integer code
    unknown_code      integer code used for unlisted characters
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


_CHAR_MAP = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}
_UNKNOWN = 5

# Keep in sync with src/task/step/steps/_sequence_common.PROTEIN_MAP.
_PROTEIN_CHARS = tuple("ACDEFGHIKLMNPQRSTVWY*")
_PROTEIN_MAP = {ch: i for i, ch in enumerate(_PROTEIN_CHARS)}
_PROTEIN_UNKNOWN = len(_PROTEIN_MAP)

_DNA_CHARS = set("ACGTN")
_RNA_CHARS = set("ACGUN")
_PROTEIN_RESIDUES = set("ACDEFGHIKLMNPQRSTVWYBXZJOU*")

_ALPHABETS = ("auto", "dna", "rna", "protein")


class FastaReader(Reader):
    """Reader for .fasta / .fa / .fna / .faa files."""
    provider = 'operon-readers'
    parameters_file = 'fasta_reader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'FastaReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'FastaReader',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True},
                                       'alphabet': {'type': 'string'},
                                       'representation': {'type': 'string', 'const': 'sequence_codes'},
                                       'alphabet_map': {'type': 'object'},
                                       'unknown_code': {'type': 'integer'},
                                       'sequences': {'type': 'array', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'extensions': ['.fasta', '.fa', '.fna', '.faa'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sequence', 'position'],
                    'labels': {'sequence': 'builtin', 'position': 'auto'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"FASTA reader requires exactly two dims, got {dims}"
            )
        sequence_dim, position_dim = dims[0], dims[1]

        requested = str(args.get("alphabet", "auto") or "auto").strip().lower()
        if requested not in _ALPHABETS:
            raise ReaderError(
                f"FASTA reader: alphabet must be one of {list(_ALPHABETS)}, "
                f"got {requested!r}"
            )

        ids, seqs = _parse_fasta(path)
        if not ids:
            raise ReaderError("FASTA file contains no sequences")

        max_len = max(len(s) for s in seqs)
        n = len(ids)

        alphabet = _infer_alphabet(seqs) if requested == "auto" else requested
        if alphabet == "protein":
            codes = _PROTEIN_MAP
            unknown = _PROTEIN_UNKNOWN
        else:
            codes = _CHAR_MAP
            unknown = _UNKNOWN

        data = np.full((n, max_len), np.nan, dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = codes.get(ch.upper(), unknown)

        final: dict[str, dict[str, int]] = {}

        seq_rule = labels.get(sequence_dim, "builtin")
        if seq_rule in (None, "builtin"):
            final[sequence_dim] = unique_labels(ids, sequence_dim, "fasta")
        elif seq_rule == "auto":
            final[sequence_dim] = {str(i): i for i in range(n)}
        elif isinstance(seq_rule, dict):
            final[sequence_dim] = {
                str(k): int(v) for k, v in seq_rule.items()
            }
        else:
            raise ReaderError(
                f"FASTA reader: unsupported label rule for "
                f"'{sequence_dim}': {seq_rule!r}"
            )

        pos_rule = labels.get(position_dim, "auto")
        if pos_rule in (None, "auto"):
            final[position_dim] = {
                str(i): i for i in range(max_len)
            }
        elif isinstance(pos_rule, dict):
            final[position_dim] = {
                str(k): int(v) for k, v in pos_rule.items()
            }
        else:
            raise ReaderError(
                f"FASTA reader: unsupported label rule for "
                f"'{position_dim}': {pos_rule!r}"
            )

        info: dict = {
            "missing_code": np.nan,
            "sequences": list(seqs),
            "alphabet": alphabet,
            "representation": "sequence_codes",
            "alphabet_map": dict(codes),
            "unknown_code": unknown,
        }

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
        )


def _parse_fasta(path: Path) -> tuple[list[str], list[str]]:
    ids: list[str] = []
    seqs: list[str] = []
    current: list[str] = []
    seen_header = False

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith(">"):
                if seen_header:
                    # An empty record still occupies one row and one label.
                    seqs.append("".join(current))
                current = []
                header = line[1:].strip()
                parts = header.split()
                sid = parts[0] if parts else f"seq{len(ids)}"
                ids.append(sid)
                seen_header = True
            else:
                if not seen_header:
                    raise ReaderError(
                        "FASTA sequence data appears before the first '>' header"
                    )
                current.append(line.rstrip())

    if seen_header:
        seqs.append("".join(current))

    return ids, seqs


def _infer_alphabet(seqs: list[str]) -> str:
    observed: set[str] = set()
    for seq in seqs:
        observed |= {c.upper() for c in seq}
    observed.discard("-")
    observed.discard(".")

    if not observed:
        return "dna"
    # Protein-specific and unknown residues must not become DNA merely because
    # their letters overlap with nucleotide ambiguity codes.
    if observed & set("EFILPQXZJ*"):
        return "protein"
    if observed <= _DNA_CHARS:
        return "dna"
    if observed <= _RNA_CHARS:
        return "rna"
    if observed <= (_DNA_CHARS | _RNA_CHARS):
        # A mixed T/U file is still nucleotide; U marks the RNA reading.
        return "rna" if "U" in observed else "dna"
    if observed <= _PROTEIN_RESIDUES:
        return "protein"
    return "protein"
