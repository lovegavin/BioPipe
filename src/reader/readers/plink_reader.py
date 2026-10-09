# src/reader/readers/plink_reader.py
"""PLINK 1.x reader.

Reads a .bed / .bim / .fam triplet into a Form.

Layout is the natural PLINK order:
    axis 0 = variant, axis 1 = sample.
``dims`` names the two axes in that order.

Labels come from the files:
    variant axis — the ID column of the .bim file
    sample axis  — the IID column of the .fam file

A1 is the ALT allele (effect allele), A2 is the REF allele.
Dosage counts A1 copies. Missing calls become NaN.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from bed_reader import open_bed

from src.core import Form, ReaderError
from src.reader.base import Reader


_BIM_COLUMNS = ["CHROM", "ID", "CM", "POS", "A1", "A2"]
_FAM_COLUMNS = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]


class PlinkReader(Reader):
    """Reader for PLINK 1.x .bed / .bim / .fam triplets."""

    extensions = [".bed"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "PLINK reader expects dims as a two-element list, "
                "e.g. dims: [variant, sample]"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        path = Path(path)
        bim_path = path.with_suffix(".bim")
        fam_path = path.with_suffix(".fam")

        for p in (path, bim_path, fam_path):
            if not p.exists():
                raise ReaderError(
                    f"PLINK component missing: {p}\n"
                    f"  Expected stem: {path.with_suffix('')}"
                )

        # --- 1. Read .bed (n_samples, n_snps) → transpose to (n_snps, n_samples)
        bed = open_bed(str(path))
        raw = bed.read(dtype="float32")
        data = np.where(np.isnan(raw), np.nan, raw).T
        data = data.astype(np.float32)

        # --- 2. Read .bim
        bim = pd.read_csv(
            bim_path, sep=r"\s+", header=None, dtype=str,
            names=_BIM_COLUMNS,
        )
        if bim.shape[0] != data.shape[0]:
            raise ReaderError(
                f".bim has {bim.shape[0]} rows but .bed has "
                f"{data.shape[0]} variants"
            )

        # --- 3. Read .fam
        fam = pd.read_csv(
            fam_path, sep=r"\s+", header=None, dtype=str,
            names=_FAM_COLUMNS,
        )
        if fam.shape[0] != data.shape[1]:
            raise ReaderError(
                f".fam has {fam.shape[0]} rows but .bed has "
                f"{data.shape[1]} samples"
            )

        # --- 4. Build labels
        variant_ids = bim["ID"].astype(str).tolist()
        sample_ids = fam["IID"].astype(str).tolist()

        # --- 5. Info
        chromosomes = sorted(bim["CHROM"].unique().tolist())
        a1_counts = bim["A1"].value_counts().to_dict()

        info = {
            "missing_code": np.nan,
            "source_format": "plink",
            "encoding": "alt_count",
            "ploidy": 2,
            "n_variants": int(bim.shape[0]),
            "n_samples": int(fam.shape[0]),
            "bim_columns": list(_BIM_COLUMNS),
            "fam_columns": list(_FAM_COLUMNS),
            "chromosomes": chromosomes,
            "a1_alleles": {str(k): int(v) for k, v in a1_counts.items()},
        }

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(sample_ids)},
            },
            info=info,
        )