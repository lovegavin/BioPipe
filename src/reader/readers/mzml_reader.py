"""mzML mass-spectrometry run summary reader.

The reader intentionally summarizes spectra instead of materializing peak
arrays: one row per ``<spectrum>`` with scan metadata and peak counts.  This
keeps large LC-MS runs cheap to inspect and matches the summary-oriented
contract used by the MGF reader.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _float(value, default=np.nan) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class MzmlReader(Reader):
    """One row per mzML spectrum, with peak lists summarized."""

    output_contract = reader_contract()
    file_input = {"dims": ["spectrum", "feature"], "labels": {"spectrum": "auto", "feature": "builtin"}}
    extensions = [".mzml"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
            "max_spectra": {"type": "integer", "minimum": 1, "default": 100000},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            tree = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"mzML reader: cannot parse {path}: {exc}") from exc

        limit = int(args.get("max_spectra", 100000))
        rows = []
        row_labels = []
        for spectrum in tree.iter():
            if _local(spectrum.tag) != "spectrum":
                continue
            cv = {}
            for element in spectrum.iter():
                if _local(element.tag) != "cvParam":
                    continue
                name = (element.get("name") or "").strip().lower()
                accession = (element.get("accession") or "").strip()
                value = element.get("value")
                if name:
                    cv.setdefault(name, value)
                    if name == "scan start time":
                        cv["scan start time unit"] = element.get("unitName") or element.get("unitAccession") or ""
                if accession:
                    cv.setdefault(accession, value)
            n_peaks = _float(spectrum.get("defaultArrayLength"), 0.0)
            precursor = np.nan
            for element in spectrum.iter():
                if _local(element.tag) == "precursorMz" and (element.text or "").strip():
                    precursor = _float(element.text)
                    break
            rt = _float(cv.get("scan start time"))
            unit = str(cv.get("scan start time unit") or "").lower()
            if np.isfinite(rt) and ("minute" in unit or cv.get("UO:0000031") is not None):
                rt *= 60.0
            polarity = 0.0
            if "positive scan" in cv:
                polarity = 1.0
            elif "negative scan" in cv:
                polarity = -1.0
            if not np.isfinite(precursor):
                precursor = _float(cv.get("selected ion m/z"))
            charge = _float(cv.get("charge state"))
            rows.append([
                _float(cv.get("ms level"), 0.0),
                rt,
                precursor,
                charge,
                n_peaks,
                _float(cv.get("base peak intensity")),
                _float(cv.get("total ion current")),
                _float(cv.get("scan window lower limit")),
                _float(cv.get("scan window upper limit")),
                polarity,
            ])
            row_labels.append(spectrum.get("id") or f"scan:{spectrum.get('index', len(rows))}")
            if len(rows) >= limit:
                break
        if not rows:
            raise ReaderError("mzML reader: no <spectrum> records found")
        frame = pd.DataFrame(rows, columns=[
            "ms_level", "retention_time", "precursor_mz", "precursor_charge",
            "n_peaks", "base_peak_intensity", "total_ion_current",
            "scan_start_mz", "scan_end_mz", "polarity",
        ])
        return table_form(
            frame, dims, labels, "mzML",
            encoders_cfg=args.get("encoders") or {},
            row_labels=row_labels,
            info_extra={"format": "mzML", "n_spectra": len(rows)},
        )
