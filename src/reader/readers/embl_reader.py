"""EMBL flat-file sequence reader.

Each record becomes one row with id, accession, description, organism,
sequence length, GC fraction and feature count. Sequence letters are
not retained."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class EmblReader(Reader):
    """EMBL flat-file reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["record", "field"], "labels": {"record": "auto", "field": "builtin"}}
    extensions = [".embl"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"EMBL reader requires exactly two dims, got {dims}")
        rows = []
        cur = {"id": "", "accession": "", "description": [], "organism": "", "sequence": [], "features": 0}
        in_sequence = False
        for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.rstrip()
            if line.startswith("ID   "):
                cur["id"] = line[5:].split(";")[0].strip()
            elif line.startswith("AC   "):
                cur["accession"] = line[5:].strip().rstrip(";")
            elif line.startswith("DE   "):
                cur["description"].append(line[5:].strip())
            elif line.startswith("OS   "):
                cur["organism"] = (cur["organism"] + " " + line[5:].strip()).strip()
            elif line.startswith("FT   "):
                cur["features"] += 1
            elif line.startswith("SQ   "):
                in_sequence = True
            elif line.startswith("//"):
                if not cur["id"]:
                    raise ReaderError("EMBL reader: record has no ID line")
                seq = "".join(cur["sequence"]).upper()
                length = len(seq)
                gc = float((seq.count("G") + seq.count("C")) / length) if length else float("nan")
                rows.append([cur["id"], cur["accession"], " ".join(cur["description"]).strip(),
                             cur["organism"], length, gc, cur["features"]])
                cur = {"id": "", "accession": "", "description": [], "organism": "", "sequence": [], "features": 0}
                in_sequence = False
            elif in_sequence:
                cur["sequence"].append("".join(ch for ch in line if ch.isalpha()))
        if in_sequence and cur["id"]:
            seq = "".join(cur["sequence"]).upper()
            length = len(seq)
            gc = float((seq.count("G") + seq.count("C")) / length) if length else float("nan")
            rows.append([cur["id"], cur["accession"], " ".join(cur["description"]).strip(),
                         cur["organism"], length, gc, cur["features"]])
        if not rows:
            raise ReaderError("EMBL reader: no records")
        df = pd.DataFrame(rows, columns=["id", "accession", "description", "organism", "length", "gc", "features"])
        return table_form(df, dims, labels, "EMBL", encoders_cfg=args.get("encoders") or {}, row_labels=df["id"].tolist())
