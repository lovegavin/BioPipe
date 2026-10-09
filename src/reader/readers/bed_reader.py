# src/reader/readers/bed_reader.py
"""UCSC BED reader.

Reads a UCSC BED file (textual interval format) into a numeric tensor.

This reader shares the .bed extension with the PLINK 1.x reader.
Disambiguation is by the absence of .bim and .fam siblings: the
PLINK reader only claims a .bed file when both siblings exist.

Layout:
    axis 0 = interval, axis 1 = field.

The BED format is defined by UCSC and formalised as GA4GH BED v1.0.
Required columns: chrom, chromStart, chromEnd (0-based, half-open).
Optional columns: name, score, strand, thickStart, thickEnd, itemRgb,
blockCount, blockSizes, blockStarts.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder


class BedReader(Reader):
    """Reader for UCSC .bed files.

    A .bed file that has .bim or .fam siblings is a PLINK 1.x file,
    not a UCSC interval file. This reader only claims orphan .bed
    files.
    """

    extensions = [".bed"]
    excludes_siblings = [".bim", ".fam"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "BED reader expects dims as a two-element list, "
                "e.g. dims: [interval, field]"
            )
        interval_dim, field_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})
        df = pd.read_csv(path, sep=r"\s+", header=None)

        if df.shape[1] < 3:
            raise ReaderError(
                f"BED file must have at least 3 columns. "
                f"Got: {df.shape[1]}"
            )

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
            dims=[interval_dim, field_dim],
            labels={k: dict(v) for k, v in labels.items()},
            info={"missing_code": np.nan},
        )