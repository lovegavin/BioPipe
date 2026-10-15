# src/reader/readers/gaf_reader.py
"""GO Annotation File (GAF) reader.

Tab-separated, 17 fixed columns, comment lines start with ``!``.

    db                    1  source database
    db_object_id          2  database-specific identifier
    db_object_symbol      3  gene symbol
    qualifier             4  NOT / contributes_to / ...
    go_id                 5  GO term identifier
    db_reference          6  reference
    evidence_code         7  EXP / IDA / ...
    with_from             8  supporting identifiers
    aspect                9  P / F / C
    db_object_name       10  full name
    db_object_synonym    11  pipe-separated synonyms
    db_object_type       12  protein / gene / ...
    taxon                13  NCBI taxonomy id
    date                 14  annotation date
    assigned_by          15  assigning group
    annotation_extension 16  structured extension
    gene_product_form_id 17  isoform identifier

Reference:
    https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/

Layout
------
    dims = [annotation, field]

    ``annotation`` is one row per GAF annotation line.
    ``field`` holds the 16 non-synonym column names above.

``db_object_synonym`` is a pipe-separated multi-valued column. It is
read verbatim into ``info["db_object_synonym"]`` and declared parallel
to the annotation axis. The column is removed from data so it can be
exploded downstream.

Label rules accepted:

    builtin           the standard column names above
    auto              position indices
    {<field_dim>: <k>}  read column <k> as annotation labels
    {name: pos, ...}  explicit mapping

Info fields set:

    missing_code         np.nan
    db_object_synonym    list of strings
    encoders             one encoder per non-numeric column
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels


_GAF_COLUMNS = [
    "db",
    "db_object_id",
    "db_object_symbol",
    "qualifier",
    "go_id",
    "db_reference",
    "evidence_code",
    "with_from",
    "aspect",
    "db_object_name",
    "db_object_synonym",
    "db_object_type",
    "taxon",
    "date",
    "assigned_by",
    "annotation_extension",
    "gene_product_form_id",
]

_INFO_COLUMNS = {"db_object_synonym"}
_N_COLUMNS = len(_GAF_COLUMNS)


class GafReader(Reader):
    """Reader for GO Annotation Files (.gaf)."""

    output_contract = reader_contract()

    file_input = {
        "dims": ["annotation", "field"],
        "labels": {"annotation": "auto", "field": "builtin"},
        "compression": [".gz"],
    }

    extensions = [".gaf"]
    handles_compression = True
    parameters_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"GAF reader requires exactly two dims, got {dims}"
            )
        row_dim, col_dim = dims[0], dims[1]

        if args:
            raise ReaderError(
                f"GAF reader: unknown args {sorted(args)}"
            )

        rows = _load_rows(path)
        if not rows:
            raise ReaderError(f"GAF file has no data lines: {path}")

        # Extract label rules.
        extracted: dict[str, dict[str, int]] = {}
        cols_to_drop: set[int] = set()

        for dim_name, rule in labels.items():
            if dim_name not in dims:
                raise ReaderError(
                    f"GAF reader: labels entry '{dim_name}' is not "
                    f"one of {dims}"
                )
            if rule in (None, "auto"):
                continue

            if rule == "builtin":
                if dim_name != col_dim:
                    raise ReaderError(
                        f"GAF reader: 'builtin' is only valid for the "
                        f"field dim '{col_dim}', not '{dim_name}'"
                    )
                continue

            if isinstance(rule, dict):
                if dim_name == row_dim and set(rule.keys()) == {col_dim}:
                    k = rule[col_dim]
                    if not 0 <= k < _N_COLUMNS:
                        raise ReaderError(
                            f"GAF reader: labels.{row_dim} column "
                            f"index {k} out of range "
                            f"(GAF has {_N_COLUMNS} columns)"
                        )
                    cols_to_drop.add(k)
                    values = [r[k] for r in rows]
                    extracted[row_dim] = unique_labels(
                        values, row_dim, "gaf"
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
                        f"GAF reader: unsupported label rule for "
                        f"'{dim_name}': {rule!r}"
                    )
                continue

            raise ReaderError(
                f"GAF reader: labels.{dim_name} must be 'builtin', "
                f"'auto', a mapping, or omitted; got {rule!r}"
            )

        # Extract info columns, remove them from data.
        info_extracted: dict[str, list[str]] = {}
        info_col_indices: set[int] = set()
        for idx, name in enumerate(_GAF_COLUMNS):
            if name not in _INFO_COLUMNS:
                continue
            info_extracted[name] = [r[idx] for r in rows]
            info_col_indices.add(idx)

        keep = [
            i for i in range(_N_COLUMNS)
            if i not in cols_to_drop and i not in info_col_indices
        ]
        if not keep:
            raise ReaderError(
                "GAF reader: all columns were consumed as row labels"
            )
        kept_names = [_GAF_COLUMNS[i] for i in keep]

        encoders_used: dict[str, object] = {}
        columns_data: list[np.ndarray] = []
        for idx in keep:
            name = _GAF_COLUMNS[idx]
            raw = [r[idx] for r in rows]
            encoder = get_encoder("labelencoder")
            columns_data.append(encoder.fit_transform(raw))
            encoders_used[name] = encoder

        data = np.stack(columns_data, axis=1).astype(np.float32)

        final: dict[str, dict[str, int]] = {}

        if row_dim in extracted:
            final[row_dim] = extracted[row_dim]
        else:
            final[row_dim] = {str(i): i for i in range(data.shape[0])}

        if col_dim in extracted:
            final[col_dim] = extracted[col_dim]
        else:
            rule = labels.get(col_dim)
            if rule == "builtin":
                final[col_dim] = unique_labels(
                    kept_names, col_dim, "gaf"
                )
            else:
                final[col_dim] = {
                    str(i): i for i in range(data.shape[1])
                }

        info: dict = {"missing_code": np.nan}
        info.update(info_extracted)
        if encoders_used:
            info["encoders"] = {col_dim: encoders_used}

        axis_info: dict[str, list[str]] = {}
        if info_extracted:
            axis_info[row_dim] = sorted(info_extracted.keys())

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
            axis_info=axis_info,
        )


def _load_rows(path: Path) -> list[list[str]]:
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    rows: list[list[str]] = []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or line.startswith("!"):
                continue
            parts = line.split("\t")
            if len(parts) != _N_COLUMNS:
                raise ReaderError(
                    f"GAF line has {len(parts)} columns, expected "
                    f"{_N_COLUMNS}: {line[:80]!r}"
                )
            rows.append(parts)
    return rows
