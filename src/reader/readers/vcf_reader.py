# src/reader/readers/vcf_reader.py
"""VCF reader.

Parses the GT field into per-ALT allele counts. Multi-allelic records
are split into one output row per ALT. Missing alleles become NaN.

Backed by cyvcf2 (htslib).

Layout follows the VCF specification:
    axis 0 = variant, axis 1 = sample.
The first eight fixed columns are CHROM, POS, ID, REF, ALT, QUAL,
FILTER, INFO; column nine is FORMAT; columns ten and onward are
samples. The reader consumes only GT from FORMAT.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from cyvcf2 import VCF

from src.core import Form, ReaderError
from src.reader.base import Reader


class VcfReader(Reader):
    """Reader for .vcf and .vcf.gz files."""

    extensions = [".vcf"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "VCF reader expects dims as a two-element list, "
                "e.g. dims: [variant, sample]"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        vcf = VCF(str(path))
        samples = list(vcf.samples)
        if not samples:
            raise ReaderError("VCF has no samples")

        variant_ids: list[str] = []
        rows: list[np.ndarray] = []

        for variant in vcf:
            arr = variant.genotype.array()   # (n_samples, ploidy+1)
            alleles = arr[:, :-1]
            missing = (alleles == -1).any(axis=1)

            vid = variant.ID or f"{variant.CHROM}:{variant.POS}"
            alts = variant.ALT or []
            if not alts:
                continue

            if len(alts) == 1:
                counts = (alleles == 1).sum(axis=1).astype(np.float32)
                counts[missing] = np.nan
                variant_ids.append(vid)
                rows.append(counts)
            else:
                for k, alt in enumerate(alts, start=1):
                    counts = (alleles == k).sum(axis=1).astype(np.float32)
                    counts[missing] = np.nan
                    variant_ids.append(f"{vid}:{alt}")
                    rows.append(counts)

        vcf.close()

        if not rows:
            raise ReaderError("VCF has no variant records")

        data = np.stack(rows, axis=0).astype(np.float32)

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(samples)},
            },
            info={"missing_code": np.nan},
        )