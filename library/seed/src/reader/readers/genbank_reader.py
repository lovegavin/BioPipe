"""GenBank flat-file summary reader.

One output row per LOCUS record. Original annotated records are retained as
axis-aligned metadata unless retain_records=False; numeric fields stay unchanged.
This is a dependency-free parser for the common GenBank flat-file layout.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_LOCUS_LENGTH = re.compile(r"\b(\d+)\s+bp\b", re.IGNORECASE)


class GenBankReader(Reader):
    provider = 'operon-readers'
    """Summary reader for GenBank (.gb/.gbk/.gbff) flat files."""
    parameters_file = 'genbank_reader.GenBankReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'GenBankReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Summary reader for GenBank (.gb/.gbk/.gbff) flat files',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True},
                                       'genbank_records': {'type': 'array', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Summary reader for GenBank (.gb/.gbk/.gbff) flat files.',
     'extensions': ['.gb', '.gbk', '.gbff'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['record', 'field'], 'labels': {'record': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"GenBank reader requires exactly two dims, got {dims}")
        retain = args.get('retain_records', True)
        # Line iteration avoids materializing a second whole-file copy.
        with path.open(encoding='utf-8', errors='strict') as source:
            lines = iter(source)
            return self._read_records(lines, dims, labels, args, retain)

    def _read_records(self, lines, dims, labels, args, retain):
        records, current = [], None
        in_features = in_origin = False
        for line in lines:
            if line.startswith("LOCUS"):
                if current is not None:
                    records.append(current)
                parts = line.split()
                locus = parts[1] if len(parts) > 1 else f"record:{len(records)}"
                match = _LOCUS_LENGTH.search(line)
                current = {
                    "id": locus,
                    "declared_length": int(match.group(1)) if match else None,
                    "sequence": [],
                    "features": 0,
                    "original": [line] if retain else [],
                }
                in_features = False
                in_origin = False
                continue
            if current is None:
                continue
            if retain:
                current['original'].append(line)
            if line.startswith("FEATURES"):
                in_features = True
                in_origin = False
                continue
            if line.startswith("ORIGIN"):
                in_features = False
                in_origin = True
                continue
            if line.startswith("//"):
                records.append(current)
                current = None
                in_features = False
                in_origin = False
                continue
            if in_features:
                # Top-level feature keys start at column 6; qualifiers
                # start at column 22 and therefore have a space at [5].
                if len(line) > 6 and line[:5] == "     " and line[5] != " ":
                    current["features"] += 1
            elif in_origin:
                current["sequence"].append("".join(ch for ch in line if ch.isalpha()))
        if current is not None:
            records.append(current)
        if not records:
            raise ReaderError("GenBank reader: no LOCUS records")
        ids = []
        rows = []
        for i, record in enumerate(records):
            sequence = "".join(record["sequence"]).upper()
            length = len(sequence) or record["declared_length"]
            if length is None:
                raise ReaderError(f"GenBank reader: record {record['id']!r} has no length")
            gc = (sequence.count("G") + sequence.count("C")) / len(sequence) if sequence else float("nan")
            ids.append(record["id"] or f"record:{i}")
            rows.append({"length": float(length), "gc": float(gc), "features": float(record["features"])})
        frame = pd.DataFrame(rows)
        form = table_form(
            frame, dims, labels, "GenBank",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "GenBank", "n_records": len(records)},
        )
        if retain:
            form.info['genbank_records'] = [''.join(r['original']) for r in records]
            form.axis_info[dims[0]] = [*form.axis_info.get(dims[0], []), 'genbank_records']
        return form
