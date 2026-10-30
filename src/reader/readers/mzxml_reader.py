"""mzXML mass-spectrometry run summary reader."""
from __future__ import annotations

import base64
import re
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

_RT = re.compile(r"PT([0-9.eE+-]+)S")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(value, default=np.nan) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _retention_seconds(value) -> float:
    if value is None:
        return np.nan
    match = _RT.fullmatch(value.strip())
    if match:
        return float(match.group(1))
    return _float(value)


def _peak_count(element) -> int:
    declared = element.get("peaksCount")
    if declared is not None:
        try:
            return int(declared)
        except ValueError:
            pass
    text = "".join(element.itertext()).strip()
    if not text:
        return 0
    try:
        raw = base64.b64decode(text)
        if element.get("compressionType", "").lower() == "zlib":
            raw = zlib.decompress(raw)
        return len(raw) // 8
    except (ValueError, zlib.error):
        return 0


class MzxmlReader(Reader):
    """One row per mzXML scan; peak arrays are only counted."""

    output_contract = reader_contract()
    file_input = {"dims": ["scan", "feature"], "labels": {"scan": "auto", "feature": "builtin"}}
    extensions = [".mzxml"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
            "max_scans": {"type": "integer", "minimum": 1, "default": 100000},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            tree = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"mzXML reader: cannot parse {path}: {exc}") from exc

        limit = int(args.get("max_scans", 100000))
        rows = []
        row_labels = []
        for scan in tree.iter():
            if _local(scan.tag) != "scan":
                continue
            precursor = np.nan
            charge = np.nan
            for child in scan.iter():
                if _local(child.tag) != "precursorMz":
                    continue
                precursor = _float((child.text or "").strip())
                charge = _float(child.get("precursorCharge"))
                break
            polarity = 1.0 if scan.get("polarity") == "+" else (-1.0 if scan.get("polarity") == "-" else 0.0)
            peaks = 0
            for child in scan:
                if _local(child.tag) == "peaks":
                    peaks = _peak_count(child)
                    break
            if peaks == 0:
                peaks = int(_float(scan.get("peaksCount"), 0.0))
            rows.append([
                _float(scan.get("msLevel"), 0.0),
                _retention_seconds(scan.get("retentionTime")),
                precursor,
                charge,
                peaks,
                _float(scan.get("basePeakMz")),
                _float(scan.get("basePeakIntensity")),
                _float(scan.get("totIonCurrent")),
                _float(scan.get("lowMz")),
                _float(scan.get("highMz")),
                polarity,
            ])
            row_labels.append(f"scan:{scan.get('num', len(rows))}")
            if len(rows) >= limit:
                break
        if not rows:
            raise ReaderError("mzXML reader: no <scan> records found")
        frame = pd.DataFrame(rows, columns=[
            "ms_level", "retention_time", "precursor_mz", "precursor_charge",
            "n_peaks", "base_peak_mz", "base_peak_intensity", "total_ion_current",
            "low_mz", "high_mz", "polarity",
        ])
        return table_form(
            frame, dims, labels, "mzXML",
            encoders_cfg=args.get("encoders") or {},
            row_labels=row_labels,
            info_extra={"format": "mzXML", "n_scans": len(rows)},
        )
