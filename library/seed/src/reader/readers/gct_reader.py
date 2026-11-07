"""GCT gene-expression reader (GCT 1.2 and 1.3)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class GctReader(Reader):
    provider = 'operon-readers'
    """Reader for .gct expression matrices; output is sample x gene."""
    parameters_file = 'gct_reader.GctReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'GctReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for .gct expression matrices; output is sample x gene',
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
     'description': 'Reader for .gct expression matrices; output is sample x gene.',
     'extensions': ['.gct'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['sample', 'gene'], 'labels': {'sample': 'builtin', 'gene': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"GCT reader requires exactly two dims, got {dims}")
        sample_dim, gene_dim = dims
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ReaderError(f"GCT reader: cannot read {path}: {exc}") from exc
        if len(lines) < 3:
            raise ReaderError("GCT reader: file has fewer than 3 lines")
        version = lines[0].strip()
        if version not in ("#1.2", "#1.3"):
            raise ReaderError(f"GCT reader: unsupported version line {version!r}")
        shape = lines[1].split()
        try:
            n_rows, n_cols = int(shape[0]), int(shape[1])
        except (ValueError, IndexError) as exc:
            raise ReaderError(f"GCT reader: invalid shape line {lines[1]!r}") from exc
        header = lines[2].split("\t")
        if len(header) != n_cols + 2:
            raise ReaderError(
                f"GCT reader: header has {len(header)} columns, expected {n_cols + 2}"
            )
        sample_ids = header[2:]
        genes, descriptions, rows = [], [], []
        for line in lines[3:]:
            if not line.strip():
                continue
            fields = line.split("\t")
            if len(fields) != n_cols + 2:
                raise ReaderError(
                    f"GCT reader: data row has {len(fields)} columns, expected {n_cols + 2}"
                )
            genes.append(fields[0])
            descriptions.append(fields[1])
            values = []
            for raw in fields[2:]:
                token = raw.strip()
                if token == "" or token.lower() in {"na", "nan", "null", "--"}:
                    values.append(float("nan"))
                    continue
                try:
                    values.append(float(token))
                except ValueError as exc:
                    raise ReaderError(
                        f"GCT reader: non-numeric expression value in {fields[0]!r}"
                    ) from exc
            rows.append(values)
        if len(rows) != n_rows:
            raise ReaderError(f"GCT reader: expected {n_rows} data rows, got {len(rows)}")
        data = np.asarray(rows, dtype=np.float32).T
        final = {
            sample_dim: unique_labels(sample_ids, sample_dim, "gct"),
            gene_dim: unique_labels(genes, gene_dim, "gct"),
        }
        return Form(
            data=compact_numeric(data),
            dims=[sample_dim, gene_dim],
            labels=final,
            info={"missing_code": np.nan, "gene_description": dict(zip(genes, descriptions)), "gct_version": version},
        )
