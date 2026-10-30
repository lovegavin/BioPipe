"""Graph Fragment Assembly (GFA 1.x) segment reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class GfaReader(Reader):
    """GFA segment reader; links and paths are ignored."""

    output_contract = reader_contract()
    file_input = {"dims": ["segment", "field"], "labels": {"segment": "auto", "field": "builtin"}}
    extensions = [".gfa"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"GFA reader requires exactly two dims, got {dims}")
        names = []
        lengths = []
        gcs = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("#") or not line.startswith("S\t"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                raise ReaderError(f"GFA reader: malformed S line: {line!r}")
            name = parts[1]
            sequence = parts[2]
            length = None
            for tag in parts[3:]:
                if tag.startswith("LN:i:"):
                    try:
                        length = int(tag.split(":", 2)[2])
                    except ValueError:
                        pass
            if sequence != "*":
                length = len(sequence)
                gc = (sequence.upper().count("G") + sequence.upper().count("C")) / max(len(sequence), 1)
            else:
                gc = float("nan")
            if length is None:
                raise ReaderError(f"GFA reader: segment {name!r} has neither sequence nor LN tag")
            names.append(name)
            lengths.append(float(length))
            gcs.append(gc)
        if not names:
            raise ReaderError("GFA reader: no segment (S) records")
        frame = pd.DataFrame({"length": lengths, "gc": gcs})
        return table_form(
            frame, dims, labels, "GFA",
            encoders_cfg=args.get("encoders") or {},
            row_labels=names,
            info_extra={"format": "GFA", "n_segments": len(names)},
        )
