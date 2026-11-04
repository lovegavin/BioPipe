"""Helpers for the small XML mass-spectrometry readers."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import ReaderError
from src.reader.readers._table_common import table_form


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def text(elem) -> str:
    return "" if elem is None or elem.text is None else str(elem.text).strip()


def attributes(elem) -> dict:
    return {str(key).rsplit("}", 1)[-1]: value for key, value in elem.attrib.items()}


def children(elem, name: str):
    return [child for child in list(elem) if local(child.tag) == name]


def descendants(elem, name: str):
    return [child for child in elem.iter() if local(child.tag) == name]


def cv_params(elem):
    return [child for child in elem.iter() if local(child.tag) == "cvParam"]


def numeric(value, default=np.nan) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return float(default)
    return number if np.isfinite(number) else float(default)


def frame_form(records, row_labels, dims, labels, fmt, path: Path, encoders, info):
    if not records:
        raise ReaderError(f"{fmt} reader: no records found in {path}")
    frame = pd.DataFrame(records, dtype=object)
    return table_form(
        frame, dims, labels, fmt,
        encoders_cfg=encoders or {},
        row_labels=row_labels[:len(frame)],
        info_extra={"format": fmt, "n_records": len(frame), **info},
    )
