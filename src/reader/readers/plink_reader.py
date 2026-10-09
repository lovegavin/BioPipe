# src/reader/readers/plink_reader.py
"""PLINK readers: 1.x (.bed/.bim/.fam) and 2.x (.pgen/.pvar/.psam).

Both readers produce the same layout:
    axis 0 = variant, axis 1 = sample.

PLINK 2.x multi-allelic handling
--------------------------------
PLINK 2 encodes multi-allelic variants in a single PGEN record. To read
them correctly, PgenReader must receive an ``allele_idx_offsets`` array
computed from the PVAR file. Each variant's record is then expanded:
a variant with K ALT alleles produces K output rows, one per ALT.

This matches the VCF reader's behaviour: ``{id}:{alt}`` for each
split allele.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from bed_reader import open_bed

from src.core import Form, ReaderError
from src.reader.base import Reader


# --------------------------------------------------------------------- #
# PLINK 1.x
# --------------------------------------------------------------------- #

_BIM_COLUMNS = ["CHROM", "ID", "CM", "POS", "A1", "A2"]
_FAM_COLUMNS = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]


class Plink1Reader(Reader):
    """Reader for PLINK 1.x .bed / .bim / .fam triplets."""

    extensions = [".bed"]
    requires_siblings = [".bim", ".fam"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "PLINK 1.x reader expects dims as a two-element list, "
                "e.g. dims: [variant, sample]"
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

        variant_ids = bim["ID"].astype(str).tolist()
        sample_ids = fam["IID"].astype(str).tolist()

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(sample_ids)},
            },
            info={"missing_code": np.nan},
        )


# --------------------------------------------------------------------- #
# PLINK 2.x
# --------------------------------------------------------------------- #

class Plink2Reader(Reader):
    """Reader for PLINK 2.x .pgen / .pvar / .psam triplets.

    Multi-allelic variants are split into one output row per ALT allele.
    """

    extensions = [".pgen"]
    requires_siblings = [".pvar", ".psam"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "PLINK 2.x reader expects dims as a two-element list, "
                "e.g. dims: [variant, sample]"
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

        # --- 1. Parse PVAR ------------------------------------------
        pvar_df = _read_pvar(pvar_path)
        n_variants = len(pvar_df)

        # ALT column: comma-separated list of ALT alleles per variant.
        alt_lists = pvar_df["ALT"].fillna(".").astype(str).apply(
            lambda s: [] if s == "." else s.split(",")
        )
        n_alts_per_variant = alt_lists.apply(len).to_numpy()
        total_alt = int(n_alts_per_variant.sum())

        # --- 2. Parse PSAM ------------------------------------------
        psam_df = _read_psam(psam_path)
        n_samples = len(psam_df)

        # --- 3. Build allele_idx_offsets ----------------------------
        # allele_idx_offsets[i+1] - allele_idx_offsets[i] = number of
        # alleles of variant i (REF + ALT count).
        allele_idx_offsets = np.zeros(n_variants + 1, dtype=np.uintp)
        for i in range(n_variants):
            allele_idx_offsets[i + 1] = (
                allele_idx_offsets[i] + 1 + n_alts_per_variant[i]
            )

        # --- 4. Read PGEN -------------------------------------------
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

            # Allocate the full output tensor.
            data = np.full(
                (total_alt, n_samples), np.nan, dtype=np.float32
            )
            out_row = 0

            for vidx in range(n_variants):
                k = n_alts_per_variant[vidx]
                if k == 0:
                    continue

                # Read each ALT allele separately.
                for alt_idx in range(1, k + 1):
                    buf = np.empty(n_samples, dtype=np.int8)
                    reader.read(vidx, buf, allele_idx=alt_idx)
                    row = buf.astype(np.float32)
                    row[buf == -9] = np.nan
                    data[out_row] = row
                    out_row += 1

        # --- 5. Build variant labels --------------------------------
        variant_ids: list[str] = []
        base_ids = pvar_df["ID"].astype(str).tolist()
        for i, alts in enumerate(alt_lists):
            if len(alts) == 0:
                continue
            if len(alts) == 1:
                variant_ids.append(base_ids[i])
            else:
                for alt in alts:
                    variant_ids.append(f"{base_ids[i]}:{alt}")

        sample_ids = psam_df["IID"].astype(str).tolist()

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(sample_ids)},
            },
            info={"missing_code": np.nan},
        )


# --------------------------------------------------------------------- #
# .pvar / .psam parsing
# --------------------------------------------------------------------- #

def _read_pvar(path: Path) -> pd.DataFrame:
    """Read a .pvar file per the PLINK 2.0 specification.

    VCF-style:
        ##...metadata...
        #CHROM  POS  ID  REF  ALT  [QUAL  FILTER  INFO]
    BIM-style (no header):
        CHROM  ID  CM  POS  ALT  REF   (6 columns)
        CHROM  ID  POS  ALT  REF        (5 columns)
    """
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
                f"PVAR header lacks an ID column: {list(df.columns)}"
            )
        if "ALT" not in df.columns:
            raise ReaderError(
                f"PVAR header lacks an ALT column: {list(df.columns)}"
            )
        return df

    # BIM-style
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
            f"PVAR with {ncols} columns is not a recognized layout"
        )
    return pd.read_csv(
        path, sep=r"\s+", header=None, dtype=str, names=names,
    )


def _read_psam(path: Path) -> pd.DataFrame:
    """Read a .psam file per the PLINK 2.0 specification."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                header = line.rstrip("\n").lstrip("#").split("\t")
                break
        else:
            raise ReaderError(f"PSAM file has no header line: {path}")

    df = pd.read_csv(
        path, sep="\t", comment="#", header=None,
        names=header, dtype=str,
    )

    if "IID" not in df.columns:
        raise ReaderError(
            f"PSAM header must contain IID, got: {list(df.columns)}"
        )
    return df