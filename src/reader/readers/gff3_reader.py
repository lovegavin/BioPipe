# src/reader/readers/gff3_reader.py
"""GFF3 (Generic Feature Format version 3) reader.

GFF3 is a 9-column tab-delimited text format. Unlike GTF, it may
contain a header block of ``##`` directive lines before the data.
Column 9 holds attributes in the form ``key=value;key=value``.
Special characters in column 9 are percent-encoded per RFC 3986.

Layout:
    axis 0 = feature, axis 1 = field.

Attributes are kept as a single column and label-encoded. They are
not split here; a future step can parse them.

Coordinates are 1-based inclusive, per the GFF3 specification.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder


_COLUMNS = [
    "seqid", "source", "type", "start", "end",
    "score", "strand", "phase", "attributes",
]


class Gff3Reader(Reader):
    """Reader for .gff / .gff3 files."""

    extensions = [".gff", ".gff3"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "GFF3 reader expects dims as a two-element list, "
                "e.g. dims: [feature, field]"
            )
        feature_dim, field_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})

        df = pd.read_csv(
            path, sep="\t", header=None, comment="#", dtype=str,
        )

        if df.shape[1] != 9:
            raise ReaderError(
                f"GFF3 requires exactly 9 columns. Got: {df.shape[1]}"
            )

        df.columns = _COLUMNS

        pos_to_label: dict[int, str] = {}
        for mapping in labels.values():
            for lab, pos in mapping.items():
                pos_to_label[pos] = lab

        cols = []
        for col_idx in range(df.shape[1]):
            col = df.iloc[:, col_idx]

            numeric = True
            try:
                values = col.to_numpy(dtype=np.float32)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols.append(values)
                continue

            label_name = pos_to_label.get(col_idx)
            enc_name = (
                encoders_cfg.get(label_name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            cols.append(get_encoder(enc_name).fit_transform(col.tolist()))

        data = np.stack(cols, axis=1).astype(np.float32)

        return Form(
            data=data,
            dims=[feature_dim, field_dim],
            labels={k: dict(v) for k, v in labels.items()},
            info={"missing_code": np.nan},
        )