"""mzData 1.05 reader: one spectrum per row."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._xml20_common import attributes, children, descendants, frame_form, numeric


class MzdataReader(Reader):
    output_contract = reader_contract()
    file_input = {"dims": ["spectrum", "feature"], "labels": {"spectrum": "auto", "feature": "builtin"}}
    extensions = [".mzdata"]
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
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"mzData reader: cannot parse {path}: {exc}") from exc
        records = []
        row_labels = []
        max_spectra = int(args.get("max_spectra", 100000))
        for spectrum in descendants(root, "spectrum"):
            if len(records) >= max_spectra:
                break
            attrs = attributes(spectrum)
            spectrum_id = attrs.get("id") or f"spectrum:{len(records)}"
            instrument = next(iter(children(spectrum, "spectrumInstrument")), None)
            iattrs = attributes(instrument) if instrument is not None else {}
            retention = float("nan")
            base_peak = float("nan")
            total_ion = float("nan")
            n_peaks = float("nan")
            polarity = ""
            for param in descendants(spectrum, "cvParam"):
                pattrs = attributes(param)
                name = str(pattrs.get("name", "")).lower()
                value = pattrs.get("value")
                if "time in minutes" in name:
                    retention = numeric(value) * 60.0
                elif "time in seconds" in name or name == "time":
                    retention = numeric(value)
                elif "base peak intensity" in name:
                    base_peak = numeric(value)
                elif "total ion current" in name:
                    total_ion = numeric(value)
                elif "number of peaks" in name:
                    n_peaks = numeric(value)
                elif "positive" in name:
                    polarity = "positive"
                elif "negative" in name:
                    polarity = "negative"
            precursor_mz = float("nan")
            precursor_charge = float("nan")
            ion = next(iter(descendants(spectrum, "ion")), None)
            if ion is not None:
                iatts = attributes(ion)
                precursor_mz = numeric(iatts.get("mz"))
                precursor_charge = numeric(iatts.get("charge"))
            records.append({
                "spectrum_id": spectrum_id,
                "ms_level": numeric(iattrs.get("msLevel")),
                "retention_time": retention,
                "precursor_mz": precursor_mz,
                "precursor_charge": precursor_charge,
                "n_peaks": n_peaks,
                "base_peak_intensity": base_peak,
                "total_ion_current": total_ion,
                "low_mz": numeric(iattrs.get("mzRangeStart")),
                "high_mz": numeric(iattrs.get("mzRangeStop")),
                "polarity": polarity,
            })
            row_labels.append(spectrum_id)
        return frame_form(records, row_labels, dims, labels, "mzData", path,
                          args.get("encoders"), {})
