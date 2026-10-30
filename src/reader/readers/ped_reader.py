"""PLINK PED genotype table reader.

The six standard metadata columns are followed by two alleles per variant.
Dosage is the count of alleles different from the first allele observed for
that variant (0/1/2); fully missing genotypes become NaN.  PED does not carry
a reference allele, so this is an encoding convention, not a biological
reference.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class PedReader(Reader):
    """PLINK PED reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "builtin"}}
    extensions = [".ped"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"PED reader requires exactly two dims, got {dims}")
        try:
            frame = pd.read_csv(path, sep=r"\s+", header=None)
        except Exception as exc:
            raise ReaderError(f"PED reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] < 8 or (frame.shape[1] - 6) % 2:
            raise ReaderError(f"PED reader: expected 6 metadata + 2*n genotype columns, got {frame.shape[1]}")
        meta = frame.iloc[:, :6].copy()
        meta.columns = ["family", "individual", "father", "mother", "sex", "phenotype"]
        sex = pd.to_numeric(meta["sex"], errors="coerce")
        phenotype = pd.to_numeric(meta["phenotype"], errors="coerce")
        meta["sex"] = sex.mask(sex <= 0)
        meta["phenotype"] = phenotype.mask(phenotype <= 0)
        n_variants = (frame.shape[1] - 6) // 2
        for j in range(n_variants):
            alleles = frame.iloc[:, 6 + 2 * j:8 + 2 * j].astype(str)
            a = alleles.iloc[:, 0].to_numpy()
            b = alleles.iloc[:, 1].to_numpy()
            valid = ~np.isin(a, ["0", "-9", "."]) & ~np.isin(b, ["0", "-9", "."])
            reference = None
            for i in np.where(valid)[0]:
                reference = a[i]
                break
            if reference is None:
                meta[f"gt:{j + 1}"] = np.nan
                continue
            dosage = np.full(len(frame), np.nan, dtype=np.float64)
            dosage[valid] = (a[valid] != reference).astype(float) + (b[valid] != reference).astype(float)
            meta[f"gt:{j + 1}"] = dosage
        ids = meta["individual"].astype(str).tolist()
        return table_form(
            meta.drop(columns=["individual"]), dims, labels, "PED",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "PED", "genotype_encoding": "alt_allele_count", "n_variants": n_variants},
        )
