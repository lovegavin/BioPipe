# src/reader/readers/gtf_reader.py
"""GTF (Gene Transfer Format) reader.

A 9-column tab-delimited text file. No header. Lines starting with
``#`` are skipped. Column names follow the GTF specification:

    0  seqname      chromosome or scaffold name
    1  source       program or database
    2  feature      feature type (gene, transcript, exon, CDS, ...)
    3  start        1-based inclusive start
    4  end          1-based inclusive end
    5  score        floating point or '.'
    6  strand       '+', '-', or '.'
    7  frame        '0', '1', '2', or '.'
    8  attribute    semicolon-separated tag-value pairs, values in
                    double quotes: ``gene_id "ENSG...";``

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           the standard GTF column names above
    auto              position indices "0", "1", ...
    {<other_dim>: <k>}  read column <k> as the other dim's labels
                        (removed from data)
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Non-numeric columns are encoded. The encoder instance used for each
column is recorded in ``info["encoders"]``.

Reference
---------
GTF specification:
https://www.ensembl.org/info/website/upload/gff.html

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


_GTF_COLUMNS = [
    "seqname", "source", "feature", "start", "end",
    "score", "strand", "frame", "attribute",
]


class GtfReader(Reader):
    """Reader for .gtf files."""

    extensions = [".gtf"]
    handles_compression = False

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"GTF reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})
        rows = _load_rows(path)

        if not rows:
            raise ReaderError(f"GTF file has no data lines: {path}")
        ncols = len(rows[0])
        if ncols != 9:
            raise ReaderError(
                f"GTF requires exactly 9 columns, got {ncols}"
            )
        if any(len(r) != 9 for r in rows):
            raise ReaderError(
                f"GTF has inconsistent column counts: {path}"
            )

        extracted: dict[str, dict[str, int]] = {}
        cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"GTF reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"GTF reader: 'builtin' is only valid for the "
                        f"column dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < 9:
                        raise ReaderError(
                            f"GTF reader: labels.{row_dim} column "
                            f"index {k} out of range (0-8)"
                        )
                    cols_to_drop.add(k)
                    values = [r[k] for r in rows]
                    extracted[row_dim] = unique_labels(
                        values, row_dim, "gtf"
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
                        f"GTF reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"GTF reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        keep = [i for i in range(9) if i not in cols_to_drop]
        kept_names = [_GTF_COLUMNS[i] for i in keep]

        encoders_used: dict[str, object] = {}
        cols_data = []
        for old_idx in keep:
            raw = [r[old_idx] for r in rows]
            numeric = True
            try:
                values = np.asarray(raw, dtype=np.float32)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols_data.append(values)
                continue

            name = _GTF_COLUMNS[old_idx]
            enc_name = (
                encoders_cfg.get(name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            encoder = get_encoder(enc_name)
            cols_data.append(encoder.fit_transform(raw))
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
                    kept_names, col_dim, "gtf"
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


def _load_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows