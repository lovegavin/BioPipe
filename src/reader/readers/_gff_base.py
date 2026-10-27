"""Shared implementation for GFF3 and GTF annotation readers.

Both formats use the same nine-column, tab-delimited record layout and
differ only in column names (``seqid``/``seqname``, ``type``/``feature``,
``attributes``/``attribute``). Keeping one implementation prevents the
two readers from drifting apart.
"""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


class _GffLikeReader(Reader):
    """Nine-column annotation reader; subclasses supply names and extensions."""

    columns: ClassVar[list[str]] = []
    format_name: ClassVar[str] = ""
    extensions: ClassVar[list[str]] = []

    output_contract = reader_contract()
    file_input = {
        "dims": ["record", "field"],
        "labels": {"record": "auto", "field": "builtin"},
    }
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {
                "type": "object",
                "title": "Encoders",
                "description": "Per-field encoder configuration.",
                "additionalProperties": True,
            }
        },
        "additionalProperties": True,
    }


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"{self.format_name} reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        encoders_cfg = args.get("encoders", {})
        rows = _load_rows(path)

        if not rows:
            raise ReaderError(f"{self.format_name} file has no data lines: {path}")
        ncols = len(rows[0])
        if ncols != 9:
            raise ReaderError(
                f"{self.format_name} requires exactly 9 columns, got {ncols}"
            )
        if any(len(r) != 9 for r in rows):
            raise ReaderError(
                f"{self.format_name} has inconsistent column counts: {path}"
            )

        extracted: dict[str, dict[str, int]] = {}
        cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"{self.format_name} reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"{self.format_name} reader: 'builtin' is only valid for the "
                        f"column dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < 9:
                        raise ReaderError(
                            f"{self.format_name} reader: labels.{row_dim} column "
                            f"index {k} out of range (0-8)"
                        )
                    cols_to_drop.add(k)
                    values = [r[k] for r in rows]
                    extracted[row_dim] = unique_labels(
                        values, row_dim, self.format_name.lower()
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
                        f"{self.format_name} reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"{self.format_name} reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        keep = [i for i in range(9) if i not in cols_to_drop]
        kept_names = [self.columns[i] for i in keep]

        encoders_used: dict[str, object] = {}
        cols_data = []
        for old_idx in keep:
            raw = [r[old_idx] for r in rows]
            numeric = True
            try:
                values = np.asarray(raw, dtype=np.float64)
            except (ValueError, TypeError):
                numeric = False

            if numeric:
                cols_data.append(values)
                continue

            name = self.columns[old_idx]
            enc_name = (
                encoders_cfg.get(name)
                or encoders_cfg.get("all")
                or "labelencoder"
            )
            encoder = get_encoder(enc_name)
            cols_data.append(encoder.fit_transform(raw))
            encoders_used[name] = encoder

        data = compact_numeric(np.stack(cols_data, axis=1))

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
                    kept_names, col_dim, self.format_name.lower()
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
            line = line.rstrip("\r\n")
            if line.startswith("##FASTA"):
                break
            if not line.strip() or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows
