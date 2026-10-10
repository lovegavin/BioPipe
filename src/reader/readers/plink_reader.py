# src/reader/readers/plink_reader.py
"""PLINK readers: 1.x (.bed/.bim/.fam) and 2.x (.pgen/.pvar/.psam).

Both readers produce the same layout:

    axis 0 = variant, axis 1 = sample.

PLINK 1.x
---------
    .bed    binary genotype matrix, variant-major (mode byte 0x01)
    .bim    variant metadata: CHROM ID CM POS A1 A2
    .fam    sample metadata:  FID IID PID MID SEX PHENO

PLINK 2.x
---------
    .pgen   binary genotype matrix
    .pvar   variant metadata (VCF-style or BIM-style header)
    .psam   sample metadata (header starts with #FID or #IID)

Routing
-------
A .bed is claimed by Plink1Reader only when .bim and .fam siblings
exist. Otherwise it is claimed by BedReader.
A .pgen is claimed by Plink2Reader only when .pvar and .psam siblings
exist.

Both readers declare ``handles_compression = True`` because their
sibling files must stay next to the target; the framework cannot
decompress to a temporary directory without breaking the sibling
lookups.

Variant ID policy
-----------------
    ID present, single ALT   use the ID as-is
    ID present, multi ALT    ``{id}:{alt}`` per split row
    ID missing               ``{CHROM}:{POS}:{ALT}`` per row
                             (PLINK 1.x uses A1 in place of ALT)

Label rules accepted
--------------------
    builtin           variant: ID column
                      sample:  IID column
    auto              position indices ``"0"``, ``"1"``, ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set
---------------
    missing_code      ``np.nan``
    ploidy            ``2``
    chrom             ``list[str]``, length = number of variant rows
    pos               ``list[int]``, length = number of variant rows

The ``chrom`` and ``pos`` arrays are parallel to the variant axis and
are kept in sync when the axis is subset (see ``Form.subset_axis``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from bed_reader import open_bed

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


_BIM_COLUMNS = ["CHROM", "ID", "CM", "POS", "A1", "A2"]
_FAM_COLUMNS = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]


# --------------------------------------------------------------------- #
# PLINK 1.x
# --------------------------------------------------------------------- #

class Plink1Reader(Reader):
    """Reader for PLINK 1.x .bed / .bim / .fam triplets."""

    extensions = [".bed"]
    requires_siblings = [".bim", ".fam"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"PLINK 1.x reader requires exactly two dims, got {dims}"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        path = Path(path)
        bim_path = path.with_suffix(".bim")
        fam_path = path.with_suffix(".fam")

        bed = open_bed(str(path))
        raw = bed.read(dtype="float32")
        data = np.where(np.isnan(raw), np.nan, raw).T.astype(np.float32)

        bim = pd.read_csv(
            bim_path, sep=r"\s+", header=None, dtype=str,
            names=_BIM_COLUMNS,
        )
        fam = pd.read_csv(
            fam_path, sep=r"\s+", header=None, dtype=str,
            names=_FAM_COLUMNS,
        )

        if bim.shape[0] != data.shape[0]:
            raise ReaderError(
                f".bim has {bim.shape[0]} rows but .bed has "
                f"{data.shape[0]} variants"
            )
        if fam.shape[0] != data.shape[1]:
            raise ReaderError(
                f".fam has {fam.shape[0]} rows but .bed has "
                f"{data.shape[1]} samples"
            )

        variant_ids = _ids_from_bim(bim)
        sample_ids = fam["IID"].astype(str).tolist()

        final = _resolve_labels(
            labels, variant_dim, sample_dim,
            variant_ids, sample_ids, "plink1",
        )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "ploidy": 2,
                "chrom": bim["CHROM"].astype(str).tolist(),
                "pos": bim["POS"].astype(int).tolist(),
            },
            axis_info={variant_dim: ["chrom", "pos"]},
        )


# --------------------------------------------------------------------- #
# PLINK 2.x
# --------------------------------------------------------------------- #

class Plink2Reader(Reader):
    """Reader for PLINK 2.x .pgen / .pvar / .psam triplets."""

    extensions = [".pgen"]
    requires_siblings = [".pvar", ".psam"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"PLINK 2.x reader requires exactly two dims, got {dims}"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        path = Path(path)
        pvar_path = path.with_suffix(".pvar")
        psam_path = path.with_suffix(".psam")

        try:
            import pgenlib
        except ImportError as exc:
            raise ReaderError(
                "pgenlib is required to read PLINK 2.x files. "
                "Install it with: pip install Pgenlib"
            ) from exc

        pvar_df = _read_pvar(pvar_path)
        n_variants = len(pvar_df)

        alt_lists = pvar_df["ALT"].fillna(".").astype(str).apply(
            lambda s: [] if s == "." else s.split(",")
        )
        n_alts_per_variant = alt_lists.apply(len).to_numpy()
        total_alt = int(n_alts_per_variant.sum())

        psam_df = _read_psam(psam_path)
        n_samples = len(psam_df)

        allele_idx_offsets = np.zeros(n_variants + 1, dtype=np.uintp)
        for i in range(n_variants):
            allele_idx_offsets[i + 1] = (
                allele_idx_offsets[i] + 1 + n_alts_per_variant[i]
            )

        with pgenlib.PgenReader(
            str(path).encode(),
            raw_sample_ct=n_samples,
            variant_ct=n_variants,
            allele_idx_offsets=allele_idx_offsets,
        ) as reader:
            if reader.get_raw_sample_ct() != n_samples:
                raise ReaderError(
                    f".pgen has {reader.get_raw_sample_ct()} samples "
                    f"but .psam has {n_samples}"
                )
            if reader.get_variant_ct() != n_variants:
                raise ReaderError(
                    f".pgen has {reader.get_variant_ct()} variants "
                    f"but .pvar has {n_variants}"
                )

            data = np.full(
                (total_alt, n_samples), np.nan, dtype=np.float32
            )
            out_row = 0

            for vidx in range(n_variants):
                k = n_alts_per_variant[vidx]
                if k == 0:
                    continue
                for alt_idx in range(1, k + 1):
                    buf = np.empty(n_samples, dtype=np.int8)
                    reader.read(vidx, buf, allele_idx=alt_idx)
                    row = buf.astype(np.float32)
                    row[buf == -9] = np.nan
                    data[out_row] = row
                    out_row += 1

        base_ids = _ids_from_pvar(pvar_df)
        chrom_col = pvar_df["CHROM"].astype(str).tolist()
        pos_col = pvar_df["POS"].astype(int).tolist()

        variant_ids: list[str] = []
        chroms: list[str] = []
        positions: list[int] = []

        for i, alts in enumerate(alt_lists):
            if len(alts) == 0:
                continue
            if len(alts) == 1:
                variant_ids.append(base_ids[i])
                chroms.append(chrom_col[i])
                positions.append(pos_col[i])
            else:
                for alt in alts:
                    variant_ids.append(f"{base_ids[i]}:{alt}")
                    chroms.append(chrom_col[i])
                    positions.append(pos_col[i])

        sample_ids = psam_df["IID"].astype(str).tolist()

        final = _resolve_labels(
            labels, variant_dim, sample_dim,
            variant_ids, sample_ids, "plink2",
        )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "ploidy": 2,
                "chrom": chroms,
                "pos": positions,
            },
            axis_info={variant_dim: ["chrom", "pos"]},
        )


# --------------------------------------------------------------------- #
# .pvar / .psam parsing
# --------------------------------------------------------------------- #

def _read_pvar(path: Path) -> pd.DataFrame:
    header: list[str] | None = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                header = line.rstrip("\n").lstrip("#").split("\t")
            break

    if header is not None:
        df = pd.read_csv(
            path, sep="\t", comment="#", header=None,
            names=header, dtype=str,
        )
        if "FORMAT" in df.columns:
            df = df.loc[:, :"FORMAT"].iloc[:, :-1]
        if "ID" not in df.columns:
            raise ReaderError(
                f"PVAR header lacks ID: {list(df.columns)}"
            )
        if "ALT" not in df.columns:
            raise ReaderError(
                f"PVAR header lacks ALT: {list(df.columns)}"
            )
        return df

    first_data = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                first_data = line
                break
    if first_data is None:
        raise ReaderError(f"PVAR file is empty: {path}")

    ncols = len(first_data.split())
    if ncols >= 6:
        names = ["CHROM", "ID", "CM", "POS", "ALT", "REF"]
    elif ncols == 5:
        names = ["CHROM", "ID", "POS", "ALT", "REF"]
    else:
        raise ReaderError(
            f"PVAR with {ncols} columns is not recognized"
        )
    return pd.read_csv(
        path, sep=r"\s+", header=None, dtype=str, names=names,
    )


def _read_psam(path: Path) -> pd.DataFrame:
    header: list[str] | None = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                header = line.rstrip("\n").lstrip("#").split("\t")
                break
    if header is None:
        raise ReaderError(f"PSAM has no header: {path}")

    df = pd.read_csv(
        path, sep="\t", comment="#", header=None,
        names=header, dtype=str,
    )
    if "IID" not in df.columns:
        raise ReaderError(
            f"PSAM header must contain IID, got {list(df.columns)}"
        )
    return df


# --------------------------------------------------------------------- #
# Variant ID derivation
# --------------------------------------------------------------------- #

def _ids_from_bim(bim: pd.DataFrame) -> list[str]:
    ids: list[str] = []
    for _, row in bim.iterrows():
        vid = str(row["ID"])
        if vid in (".", ""):
            vid = f"{row['CHROM']}:{row['POS']}:{row['A1']}"
        ids.append(vid)
    return ids


def _ids_from_pvar(pvar_df: pd.DataFrame) -> list[str]:
    has_pos = "POS" in pvar_df.columns
    has_chrom = "CHROM" in pvar_df.columns
    ids: list[str] = []
    for _, row in pvar_df.iterrows():
        vid = str(row["ID"])
        if vid in (".", ""):
            if has_pos and has_chrom:
                vid = f"{row['CHROM']}:{row['POS']}"
            else:
                vid = "."
        ids.append(vid)
    return ids


# --------------------------------------------------------------------- #
# Label resolution
# --------------------------------------------------------------------- #

def _resolve_labels(
    labels: dict,
    variant_dim: str,
    sample_dim: str,
    variant_ids: list[str],
    sample_ids: list[str],
    source: str,
) -> dict[str, dict[str, int]]:
    final: dict[str, dict[str, int]] = {}

    for dim_name, builtin in (
        (variant_dim, variant_ids),
        (sample_dim, sample_ids),
    ):
        rule = labels.get(dim_name, "builtin")

        if rule in (None, "builtin"):
            final[dim_name] = unique_labels(builtin, dim_name, source)
        elif rule == "auto":
            final[dim_name] = {
                str(i): i for i in range(len(builtin))
            }
        elif isinstance(rule, dict):
            final[dim_name] = {
                str(k): int(v) for k, v in rule.items()
            }
        else:
            raise ReaderError(
                f"PLINK reader: unsupported label rule for "
                f"'{dim_name}': {rule!r}"
            )

    return final