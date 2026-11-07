"""Mascot Generic Format (MGF) spectrum summary reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class MgfReader(Reader):
    provider = 'operon-readers'
    """MGF reader returning one row per spectrum (peak lists are summarized)."""
    parameters_file = 'mgf_reader.MgfReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'MgfReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'MGF reader returning one row per spectrum (peak lists are summarized)',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'MGF reader returning one row per spectrum (peak lists are summarized).',
     'extensions': ['.mgf'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['spectrum', 'feature'],
                    'labels': {'spectrum': 'auto', 'feature': 'builtin'}}}


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
                current = {"pepmass": np.nan, "charge": np.nan, "rt": np.nan, "title": "", "precursor_mz": np.nan}
                peaks = []
            elif upper == "END IONS":
                if current is None:
                    raise ReaderError("MGF reader: END IONS without BEGIN IONS")
                if not peaks:
                    current["n_peaks"] = 0; current["base_peak"] = 0.0
                    current["precursor_mz"] = current["pepmass"]
                else:
                    mz, intensity = zip(*peaks)
                    current["n_peaks"] = len(peaks)
                    current["base_peak"] = float(max(intensity))
                    if not np.isfinite(current["precursor_mz"]):
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
