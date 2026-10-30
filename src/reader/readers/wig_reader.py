"""WIG fixedStep/variableStep signal track reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


def _attrs(line: str, name: str) -> dict:
    out = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            out[key] = value
    return out


class WigReader(Reader):
    """Reader for fixedStep and variableStep WIG tracks; output is region x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".wig"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_records": {"type": "integer", "minimum": 1, "default": 1000000},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        max_records = int(args.get("max_records", 1000000))
        rows = []
        labels_region = []
        chrom = None
        mode = None
        pos = 0
        step = 1
        span = 1
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"WIG reader: cannot read {path}: {exc}") from exc
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("track") or line.startswith("browser"):
                continue
            if line.startswith("fixedStep"):
                attrs = _attrs(line, "fixedStep")
                if "chrom" not in attrs or "start" not in attrs:
                    raise ReaderError("WIG reader: fixedStep requires chrom and start")
                chrom = attrs["chrom"]
                pos = int(attrs["start"])
                step = int(attrs.get("step", 1))
                span = int(attrs.get("span", 1))
                mode = "fixed"
                continue
            if line.startswith("variableStep"):
                attrs = _attrs(line, "variableStep")
                if "chrom" not in attrs:
                    raise ReaderError("WIG reader: variableStep requires chrom")
                chrom = attrs["chrom"]
                span = int(attrs.get("span", 1))
                mode = "variable"
                continue
            if mode == "fixed":
                if len(rows) >= max_records:
                    break
                if chrom is None:
                    raise ReaderError("WIG reader: value before fixedStep header")
                start0 = pos - 1
                rows.append([chrom, start0, start0 + span, float(line)])
                labels_region.append(f"{chrom}:{start0}-{start0 + span}")
                pos += step
            elif mode == "variable":
                fields = line.split()
                if len(fields) != 2:
                    raise ReaderError(f"WIG reader: expected 'position value', got {line!r}")
                if len(rows) >= max_records:
                    break
                p = int(fields[0])
                start0 = p - 1
                rows.append([chrom, start0, start0 + span, float(fields[1])])
                labels_region.append(f"{chrom}:{start0}-{start0 + span}")
            else:
                raise ReaderError(f"WIG reader: data before fixedStep/variableStep header: {line!r}")
        if not rows:
            raise ReaderError(f"WIG reader: no data records in {path}")
        df = pd.DataFrame(rows, columns=["chrom", "start", "end", "value"])
        return table_form(
            df, dims, labels, "WIG", args.get("encoders", {}),
            row_labels=labels_region,
        )
