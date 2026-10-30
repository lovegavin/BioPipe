"""GenBank flat-file summary reader.

One output row per LOCUS record.  The sequence itself is not returned;
``length``, GC fraction and the number of top-level feature keys are.
This is a dependency-free parser for the common GenBank flat-file layout.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_LOCUS_LENGTH = re.compile(r"\b(\d+)\s+bp\b", re.IGNORECASE)


class GenBankReader(Reader):
    """Summary reader for GenBank (.gb/.gbk/.gbff) flat files."""

    output_contract = reader_contract()
    file_input = {"dims": ["record", "field"], "labels": {"record": "auto", "field": "builtin"}}
    extensions = [".gb", ".gbk", ".gbff"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"GenBank reader requires exactly two dims, got {dims}")
        records = []
        current = None
        in_features = False
        in_origin = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
                }
                in_features = False
                in_origin = False
                continue
            if current is None:
                continue
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
        return table_form(
            frame, dims, labels, "GenBank",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "GenBank", "n_records": len(records)},
        )
