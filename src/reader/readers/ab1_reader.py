"""ABIF/AB1 Sanger chromatogram reader.

ABIF files are a directory of typed tags.  The reader keeps the primary
base calls, quality values and peak positions, and adds the four raw
trace values sampled at each called peak.  The full sequence is also
stored in ``info['sequence']`` so no information is lost when the table
is passed to numeric operators.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

_ABIF_TYPES = {1: "B", 3: "H", 4: "h", 5: "i", 6: "f", 7: "d"}


def _entry(raw: bytes, offset: int) -> dict:
    if offset < 0 or offset + 28 > len(raw):
        raise ReaderError("AB1 reader: truncated directory entry")
    block = raw[offset:offset + 28]
    name = block[:4].decode("latin-1", errors="replace")
    number = int.from_bytes(block[4:8], "big")
    type_id = int.from_bytes(block[8:10], "big")
    element_size = int.from_bytes(block[10:12], "big")
    count = int.from_bytes(block[12:16], "big")
    data_size = int.from_bytes(block[16:20], "big")
    data_offset = int.from_bytes(block[20:24], "big")
    return {
        "name": name,
        "number": number,
        "type": type_id,
        "element_size": element_size,
        "count": count,
        "data_size": data_size,
        "data_offset": data_offset,
    }


def _payload_at(raw: bytes, entry_offset: int, item: dict) -> bytes:
    size = int(item["data_size"])
    if size <= 4:
        return raw[entry_offset + 20:entry_offset + 20 + size]
    start = int(item["data_offset"])
    if start < 0 or start + size > len(raw):
        raise ReaderError("AB1 reader: tag payload is outside the file")
    return raw[start:start + size]


def _directory(raw: bytes) -> list[dict]:
    root = _entry(raw, 6)
    if root["name"] != "tdir" or root["type"] != 1023:
        raise ReaderError("AB1 reader: missing ABIF root directory")
    start = int(root["data_offset"])
    count = int(root["count"])
    if start < 0 or start + count * 28 > len(raw):
        raise ReaderError("AB1 reader: truncated ABIF directory")
    entries = []
    for index in range(count):
        offset = start + index * 28
        item = _entry(raw, offset)
        item["_entry_offset"] = offset
        entries.append(item)
    return entries


def _find(entries: list[dict], name: str, number: int = 1) -> dict | None:
    for item in entries:
        if item["name"] == name and item["number"] == number:
            return item
    return None


def _text(raw: bytes, entry: dict) -> str:
    payload = _payload_at(raw, entry["_entry_offset"], entry)
    if entry["type"] == 18:
        if not payload:
            return ""
        length = payload[0]
        return payload[1:1 + length].decode("utf-8", errors="replace")
    if entry["type"] == 19:
        return payload.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    return payload.decode("utf-8", errors="replace").replace("\x00", "").strip()


def _bytes(raw: bytes, entry: dict) -> np.ndarray:
    payload = _payload_at(raw, entry["_entry_offset"], entry)
    return np.frombuffer(payload, dtype=np.uint8).copy()


def _shorts(raw: bytes, entry: dict) -> np.ndarray:
    payload = _payload_at(raw, entry["_entry_offset"], entry)
    if entry["type"] == 2:
        return np.frombuffer(payload, dtype=np.uint8).astype(np.int64)
    if entry["type"] == 4:
        return np.frombuffer(payload, dtype=">i2").astype(np.int64)
    if entry["type"] == 3:
        return np.frombuffer(payload, dtype=">u2").astype(np.int64)
    if entry["type"] == 5:
        return np.frombuffer(payload, dtype=">i4").astype(np.int64)
    raise ReaderError(f"AB1 reader: unsupported numeric tag type {entry['type']}")


class Ab1Reader(Reader):
    """Reader for ABI .ab1 Sanger trace files."""

    output_contract = reader_contract()
    file_input = {
        "dims": ["base", "feature"],
        "labels": {"base": "builtin", "feature": "builtin"},
    }
    extensions = [".ab1"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_bases": {"type": "integer", "minimum": 1, "default": 1000000},
        },
        "additionalProperties": False,
    }

    @staticmethod
    def _header(path: Path) -> tuple[bytes, list[dict]]:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"AB1 reader: cannot read {path}: {exc}") from exc
        if len(raw) < 34 or raw[:4] != b"ABIF":
            raise ReaderError("AB1 reader: missing ABIF magic")
        entries = _directory(raw)
        return raw, entries

    def probe(self, path: Path, **args) -> dict:
        raw, entries = self._header(path)
        pbas = _find(entries, "PBAS")
        n_bases = len(_text(raw, pbas)) if pbas is not None else 0
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": (n_bases, 6),
            "dtype": "float64",
            "dense_bytes": n_bases * 6 * 8,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"AB1 reader requires exactly two dims, got {dims}")
        raw, entries = self._header(path)
        pbas = _find(entries, "PBAS")
        if pbas is None:
            raise ReaderError("AB1 reader: missing PBAS base-call tag")
        sequence = _text(raw, pbas)
        if not sequence:
            raise ReaderError("AB1 reader: PBAS contains no base calls")
        limit = min(len(sequence), int(args.get("max_bases", 1000000)))
        sequence = sequence[:limit]

        def numeric_tag(name: str, fallback=None):
            item = _find(entries, name)
            if item is None:
                return fallback
            return _shorts(raw, item)

        quality = numeric_tag("PCON")
        peaks = numeric_tag("PLOC")
        if quality is None:
            quality = np.full(limit, np.nan)
        if peaks is None:
            peaks = np.arange(limit)
        quality = np.asarray(quality, dtype=np.float64)[:limit]
        peaks = np.asarray(peaks, dtype=np.float64)[:limit]
        if len(quality) < limit:
            quality = np.pad(quality, (0, limit - len(quality)), constant_values=np.nan)
        if len(peaks) < limit:
            peaks = np.pad(peaks, (0, limit - len(peaks)), constant_values=np.nan)

        fwo = _find(entries, "FWO_") or _find(entries, "FWO.") or _find(entries, "FWO")
        order = _text(raw, fwo).strip().upper() if fwo is not None else "ACGT"
        if sorted(order[:4]) != sorted("ACGT"):
            order = "ACGT"
        channels = {}
        for index, base in enumerate(order[:4], start=1):
            item = _find(entries, "DATA", index)
            if item is not None:
                channels[base] = _shorts(raw, item)
        trace = {base: np.full(limit, np.nan) for base in "ACGT"}
        for base, values in channels.items():
            for index, peak in enumerate(peaks):
                if np.isfinite(peak) and 0 <= int(peak) < len(values):
                    trace[base][index] = float(values[int(peak)])

        frame = pd.DataFrame({
            "quality": quality,
            "peak_position": peaks,
            "trace_A": trace["A"],
            "trace_C": trace["C"],
            "trace_G": trace["G"],
            "trace_T": trace["T"],
        })
        base_labels = [f"{index + 1}:{base}" for index, base in enumerate(sequence)]
        sample = _find(entries, "SMPL")
        model = _find(entries, "MODL")
        info = {
            "format": "AB1",
            "n_bases": limit,
            "sequence": sequence,
            "base_order": order[:4],
            "sample": _text(raw, sample) if sample is not None else "",
            "model": _text(raw, model) if model is not None else "",
            "abif_version": int.from_bytes(raw[4:6], "big"),
        }
        return table_form(
            frame,
            dims,
            labels,
            "AB1",
            encoders_cfg={},
            row_labels=base_labels,
            col_labels=["quality", "peak_position", "trace_A", "trace_C", "trace_G", "trace_T"],
            info_extra=info,
        )
