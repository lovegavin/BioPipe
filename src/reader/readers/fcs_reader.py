"""FCS (Flow Cytometry Standard) reader.

The reader supports the list-mode integer/float/double FCS 2.0-3.1
layouts used by flowCore.  It exposes one row per event and one column
per parameter; parameter names prefer ``$PnN`` over ``$PnS`` and event
labels are stable ``event:<n>`` strings.
"""
from __future__ import annotations

import re
import struct
from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


def _field(header: bytes, start: int) -> int:
    """Read one fixed-width decimal offset from an FCS header."""
    raw = header[start:start + 8].decode("latin-1", errors="replace").strip()
    if not raw or not raw.isdigit():
        return 0
    return int(raw)


def _number(value, default=0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return int(default)


def _keyword(keywords: dict, name: str) -> str:
    for candidate in (name, name.lstrip("$"), f"${name.lstrip('$')}"):
        if candidate in keywords:
            return str(keywords[candidate]).strip()
    return ""


def _split_text(text: str) -> dict:
    """Parse the FCS TEXT segment into a keyword mapping."""
    if not text:
        return {}
    delimiter = text[0]
    body = text[1:]
    if body.endswith(delimiter):
        body = body[:-1]
    parts = body.split(delimiter)
    keywords = {}
    for index in range(0, len(parts) - 1, 2):
        key = parts[index].strip()
        value = parts[index + 1].strip()
        if key:
            keywords[key] = value
    return keywords


def _byte_order(value: str) -> tuple[bool, list[int]]:
    try:
        order = [int(part) for part in re.split(r"[,\s]+", value.strip()) if part]
    except ValueError as exc:
        raise ReaderError(f"FCS reader: invalid $BYTEORD {value!r}") from exc
    if not order:
        raise ReaderError("FCS reader: empty $BYTEORD")
    return order[0] > order[-1], order


def _decode_float(raw: bytes, big_endian: bool, double: bool) -> float:
    if len(raw) != (8 if double else 4):
        raise ReaderError("FCS reader: truncated floating-point parameter")
    fmt = (">" if big_endian else "<") + ("d" if double else "f")
    return float(struct.unpack(fmt, raw)[0])


class FcsReader(Reader):
    """Reader for .fcs flow-cytometry files."""

    output_contract = reader_contract()
    file_input = {
        "dims": ["event", "channel"],
        "labels": {"event": "auto", "channel": "builtin"},
    }
    extensions = [".fcs"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_events": {"type": "integer", "minimum": 1, "default": 1000000},
        },
        "additionalProperties": False,
    }

    @staticmethod
    def _header(path: Path) -> tuple[bytes, int, int, int, int]:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"FCS reader: cannot read {path}: {exc}") from exc
        if len(raw) < 58:
            raise ReaderError("FCS reader: file is too short")
        if raw[:3] != b"FCS":
            raise ReaderError("FCS reader: missing FCS magic")
        text_start = _field(raw, 10)
        text_end = _field(raw, 18)
        data_start = _field(raw, 26)
        data_end = _field(raw, 34)
        if not text_start or not text_end:
            raise ReaderError("FCS reader: missing TEXT segment offsets")
        if not data_start or not data_end:
            raise ReaderError("FCS reader: missing DATA segment offsets")
        return raw, text_start, text_end, data_start, data_end

    def probe(self, path: Path, **args) -> dict:
        raw, text_start, text_end, _, _ = self._header(path)
        keywords = _split_text(raw[text_start:text_end + 1].decode("latin-1", errors="replace"))
        n_events = _number(_keyword(keywords, "$TOT"))
        n_channels = _number(_keyword(keywords, "$PAR"))
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (n_events, n_channels),
            "dtype": "float64",
            "dense_bytes": n_events * n_channels * 8,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"FCS reader requires exactly two dims, got {dims}")
        raw, text_start, text_end, data_start, data_end = self._header(path)
        text = raw[text_start:text_end + 1].decode("latin-1", errors="replace")
        keywords = _split_text(text)
        if not keywords:
            raise ReaderError("FCS reader: empty TEXT segment")

        datatype = _keyword(keywords, "$DATATYPE").upper() or "I"
        if datatype == "A":
            raise ReaderError("FCS reader: ASCII ($DATATYPE=A) data is not supported")
        if datatype not in {"I", "F", "D"}:
            raise ReaderError(f"FCS reader: unsupported $DATATYPE {datatype!r}")
        mode = _keyword(keywords, "$MODE").upper() or "L"
        if mode != "L":
            raise ReaderError(f"FCS reader: unsupported $MODE {mode!r}; list mode is required")
        big_endian, order = _byte_order(_keyword(keywords, "$BYTEORD"))
        if datatype == "I" and order not in ([1, 2, 3, 4], [4, 3, 2, 1], [1, 2], [2, 1]):
            raise ReaderError(f"FCS reader: unsupported $BYTEORD {order!r} for integer data")

        n_events = _number(_keyword(keywords, "$TOT"), -1)
        n_channels = _number(_keyword(keywords, "$PAR"), -1)
        if n_events < 0 or n_channels < 1:
            raise ReaderError("FCS reader: $TOT and $PAR must be positive integers")

        channel_names = []
        bits = []
        ranges = []
        for index in range(1, n_channels + 1):
            name = _keyword(keywords, f"$P{index}N") or _keyword(keywords, f"$P{index}S")
            channel_names.append(name or f"P{index}")
            width = _number(_keyword(keywords, f"$P{index}B"), 0)
            if width <= 0:
                raise ReaderError(f"FCS reader: missing/invalid $P{index}B")
            if width > 64:
                raise ReaderError(f"FCS reader: $P{index}B={width} is unsupported")
            bits.append(width)
            ranges.append(_number(_keyword(keywords, f"$P{index}R"), 0))

        if datatype == "I":
            widths = [(value + 7) // 8 for value in bits]
        else:
            widths = [8 if datatype == "D" else 4] * n_channels
        stride = sum(widths)
        required = stride * n_events
        available = data_end - data_start + 1
        if available < required:
            raise ReaderError(
                f"FCS reader: DATA segment has {available} bytes, need {required}"
            )

        limit = min(n_events, int(args.get("max_events", 1000000)))
        data = np.empty((limit, n_channels), dtype=np.float64)
        offset = data_start
        for event in range(limit):
            for channel, width in enumerate(widths):
                chunk = raw[offset:offset + width]
                offset += width
                if len(chunk) != width:
                    raise ReaderError("FCS reader: truncated DATA segment")
                if datatype == "I":
                    value = int.from_bytes(chunk, "big" if big_endian else "little", signed=False)
                    data[event, channel] = value & ((1 << bits[channel]) - 1)
                else:
                    data[event, channel] = _decode_float(
                        chunk, big_endian, datatype == "D"
                    )

        event_labels = [f"event:{index + 1}" for index in range(limit)]
        metadata = {}
        for key in ("$CYT", "$SYS", "$CREATOR", "$DATE", "$BTIM", "$ETIM", "$SMNO", "$CELLS"):
            value = _keyword(keywords, key)
            if value:
                metadata[key] = value
        frame = pd.DataFrame(data, columns=channel_names)
        return table_form(
            frame,
            dims,
            labels,
            "FCS",
            encoders_cfg={},
            row_labels=event_labels,
            col_labels=channel_names,
            info_extra={
                "format": "FCS",
                "fcs_version": raw[3:6].decode("latin-1", errors="replace"),
                "n_events": limit,
                "n_channels": n_channels,
                "datatype": datatype,
                "byte_order": order,
                "channels": channel_names,
                "bits": bits,
                "ranges": ranges,
                "metadata": metadata,
            },
        )
