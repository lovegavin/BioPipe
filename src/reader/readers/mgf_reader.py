"""Mascot Generic Format (MGF) spectrum summary reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class MgfReader(Reader):
    """MGF reader returning one row per spectrum (peak lists are summarized)."""

    output_contract = reader_contract()
    file_input = {"dims": ["spectrum", "feature"], "labels": {"spectrum": "auto", "feature": "builtin"}}
    extensions = [".mgf"]
    handles_compression = True
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
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"MGF reader: cannot read {path}: {exc}") from exc
        max_spectra = int(args.get("max_spectra", 100000))
        rows = []; titles = []
        current = None; peaks = []
        for line in lines:
            text = line.strip()
            upper = text.upper()
            if upper == "BEGIN IONS":
                current = {"pepmass": np.nan, "charge": np.nan, "rt": np.nan, "title": ""}
                peaks = []
            elif upper == "END IONS":
                if current is None:
                    raise ReaderError("MGF reader: END IONS without BEGIN IONS")
                if not peaks:
                    current["n_peaks"] = 0; current["base_peak"] = 0.0
                else:
                    mz, intensity = zip(*peaks)
                    current["n_peaks"] = len(peaks)
                    current["base_peak"] = float(max(intensity))
                    current["precursor_mz"] = float(mz[0])
                rows.append([current["pepmass"], current["charge"], current["rt"],
                             current["n_peaks"], current["base_peak"], current["precursor_mz"]])
                titles.append(current["title"] or f"spectrum:{len(rows)}")
                current = None; peaks = []
                if len(rows) >= max_spectra:
                    break
            elif current is not None:
                if upper.startswith("TITLE="):
                    current["title"] = text.split("=", 1)[1]
                elif upper.startswith("PEPMASS="):
                    value = text.split("=", 1)[1].split()[0]
                    try: current["pepmass"] = float(value)
                    except ValueError: pass
                elif upper.startswith("CHARGE="):
                    value = text.split("=", 1)[1].split("+")[0].split("-")[0]
                    try: current["charge"] = float(value)
                    except ValueError: pass
                elif upper.startswith("RTINSECONDS="):
                    try: current["rt"] = float(text.split("=", 1)[1])
                    except ValueError: pass
                elif text and not text.startswith(("#", ";", "!")):
                    parts = text.split()
                    if len(parts) >= 2:
                        try: peaks.append((float(parts[0]), float(parts[1])))
                        except ValueError: pass
        if not rows:
            raise ReaderError("MGF reader: no complete BEGIN/END IONS spectrum")
        df = pd.DataFrame(rows, columns=["pepmass", "charge", "retention_time",
                                         "n_peaks", "base_peak_intensity", "precursor_mz"])
        return table_form(
            df, dims, labels, "MGF",
            encoders_cfg=args.get("encoders") or {},
            row_labels=titles,
            info_extra={"format": "MGF", "n_spectra": len(rows)},
        )
