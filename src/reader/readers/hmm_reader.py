"""HMMER3 profile HMM reader.

Reads NAME/LENG/ALPH/NSEQ from each profile header; alignment columns
are not materialised."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class HmmReader(Reader):
    """HMMER3 profile reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["model", "field"], "labels": {"model": "auto", "field": "builtin"}}
    extensions = [".hmm"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"HMM reader requires exactly two dims, got {dims}")
        rows = []
        cur = None
        for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith("NAME"):
                if cur is not None:
                    rows.append(cur)
                cur = {"name": line.split(None, 1)[1].strip(), "length": None, "alphabet": "", "nseq": None}
            elif cur is not None and line.startswith("LENG"):
                cur["length"] = int(line.split(None, 1)[1])
            elif cur is not None and line.startswith("ALPH"):
                cur["alphabet"] = line.split(None, 1)[1].strip()
            elif cur is not None and line.startswith("NSEQ"):
                cur["nseq"] = int(line.split(None, 1)[1])
            elif line == "//" and cur is not None:
                rows.append(cur)
                cur = None
        if cur is not None:
            rows.append(cur)
        if not rows:
            raise ReaderError("HMM reader: no profiles")
        df = pd.DataFrame(rows).fillna({"length": 0, "nseq": 0})
        return table_form(df, dims, labels, "HMM", encoders_cfg=args.get("encoders") or {}, row_labels=df["name"].tolist())
