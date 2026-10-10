# src/reader/readers/bed_reader.py
"""UCSC BED reader.

A whitespace-delimited text file with 3 to 12 columns per line. No
header. Column meaning is fixed by the BED specification:

    0  chrom         chromosome name
    1  chromStart    0-based start
    2  chromEnd      end (exclusive)
    3  name          feature name
    4  score         0-1000
    5  strand        '+' or '-'
    6  thickStart
    7  thickEnd
    8  itemRgb       R,G,B
    9  blockCount
    10 blockSizes    comma-separated
    11 blockStarts   comma-separated

``track`` and ``browser`` lines at the top are skipped.

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           the standard BED column names above
    auto              position indices "0", "1", ...
    {<other_dim>: <k>}  read column <k> as the other dim's labels
                        (removed from data)
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Non-numeric columns (chrom, name, strand, ...) are encoded. The
encoder instance used for each column is recorded in
``info["encoders"]``.

Reference
---------
UCSC BED format: https://genome.ucsc.edu/FAQ/FAQformat.html#format1
GA4GH BED v1.0 formalises the same layout.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


_BED_COLUMNS = [
    "chrom", "chromStart", "chromEnd",
    "name", "score", "strand",
    "thickStart", "thickEnd", "itemRgb",
    "blockCount", "blockSizes", "blockStarts",
]


class BedReader(Reader):
    """Reader for UCSC .bed files."""

    extensions = [".bed"]
    excludes_siblings = [".bim", ".fam", ".pgen"]
    handles_compression = False

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"BED reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})
        df = _load(path)

        if df.shape[1] < 3:
            raise ReaderError(
                f"BED file must have at least 3 columns, "
                f"got {df.shape[1]}"
            )
        if df.shape[1] > len(_BED_COLUMNS):
            raise ReaderError(
                f"BED file has {df.shape[1]} columns, at most "
                f"{len(_BED_COLUMNS)} are defined"
            )

        col_names = _BED_COLUMNS[: df.shape[1]]
        df.columns = col_names

        extracted: dict[str, dict[str, int]] = {}
        cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"BED reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"BED reader: 'builtin' is only valid for the "
                        f"column dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < df.shape[1]:
                        raise ReaderError(
                            f"BED reader: labels.{row_dim} column "
                            f"index {k} out of range "
                            f"(file has {df.shape[1]} columns)"
                        )
                    cols_to_drop.add(k)
                    values = df.iloc[:, k].astype(str).tolist()
                    extracted[row_dim] = unique_labels(
                        values, row_dim, "bed"
                    )
                elif dim_name == row_dim:
                    extracted[row_dim] = {
                        str(k): int(v) for k, v in rule.items()
                    }
                elif dim_name == col_dim:
                    extracted[col_dim] = {
                        str(k): int(v) for k, v in rule.items()
                    }
                else:
                    raise ReaderError(
                        f"BED reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"BED reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        keep = [i for i in range(df.shape[1]) if i not in cols_to_drop]
        kept_names = [col_names[i] for i in keep]

        encoders_used: dict[str, object] = {}
        cols_data = []
        for old_idx in keep:
            col = df.iloc[:, old_idx]
            numeric = True
            try:
                values = col.to_numpy(dtype=np.float32)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols_data.append(values)
                continue

            name = col_names[old_idx]
            enc_name = (
                encoders_cfg.get(name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            encoder = get_encoder(enc_name)
            cols_data.append(encoder.fit_transform(col.tolist()))
            encoders_used[name] = encoder

        data = np.stack(cols_data, axis=1).astype(np.float32)

        final: dict[str, dict[str, int]] = {}

        if row_dim in extracted:
            final[row_dim] = extracted[row_dim]
        else:
            final[row_dim] = {
                str(i): i for i in range(data.shape[0])
            }

        if col_dim in extracted:
            final[col_dim] = extracted[col_dim]
        else:
            rule = labels.get(col_dim)
            if rule == "builtin":
                final[col_dim] = unique_labels(
                    kept_names, col_dim, "bed"
                )
            else:
                final[col_dim] = {
                    str(i): i for i in range(data.shape[1])
                }

        info: dict = {"missing_code": np.nan}
        if encoders_used:
            info["encoders"] = {col_dim: encoders_used}

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
        )


def _load(path: Path) -> pd.DataFrame:
    rows: list[list[str]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("track") or line.startswith("browser"):
                continue
            rows.append(line.split())
    if not rows:
        raise ReaderError(f"BED file has no data lines: {path}")
    ncols = len(rows[0])
    if any(len(r) != ncols for r in rows):
        raise ReaderError(
            f"BED file has inconsistent column counts: {path}"
        )
    return pd.DataFrame(rows)