"""Sequential PHYLIP alignment reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3, "N": 4}


class PhylipReader(Reader):
    provider = 'operon-readers'
    """Reader for sequential PHYLIP alignments."""
    parameters_file = 'phylip_reader.PhylipReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PhylipReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for sequential PHYLIP alignments',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Reader for sequential PHYLIP alignments.',
     'extensions': ['.phy', '.phylip'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sequence', 'position'],
                    'labels': {'sequence': 'builtin', 'position': 'auto'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PHYLIP reader requires exactly two dims, got {dims}")
        seq_dim, pos_dim = dims
        names, seqs = _parse(path)
        if not seqs:
            raise ReaderError("PHYLIP reader: no sequences")
        width = len(seqs[0])
        data = np.full((len(seqs), width), np.nan, dtype=np.float32)
        for i, seq in enumerate(seqs):
            for j, ch in enumerate(seq):
                data[i, j] = _CODES.get(ch.upper(), 5)
        return Form(
            data=data,
            dims=[seq_dim, pos_dim],
            labels={
                seq_dim: unique_labels(names, seq_dim, "phylip"),
                pos_dim: {str(i): i for i in range(width)},
            },
            info={"missing_code": np.nan, "alphabet": "dna"},
        )


def _parse(path: Path):
    with open(path, encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip()]
    if not lines:
        raise ReaderError("PHYLIP reader: empty file")
    try:
        n = int(lines[0].split()[0])
    except ValueError as exc:
        raise ReaderError("PHYLIP reader: first line must start with the sequence count") from exc
    records = lines[1:]
    if len(records) < n:
        raise ReaderError(f"PHYLIP reader: expected {n} sequences, got {len(records)}")
    names, seqs = [], []
    for line in records[:n]:
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ReaderError("PHYLIP reader: each sequence needs a name and residues")
        names.append(parts[0])
        seqs.append("".join(parts[1].split()))
    width = len(seqs[0])
    if any(len(seq) != width for seq in seqs):
        raise ReaderError("PHYLIP reader: sequences have different lengths")
    return names, seqs
