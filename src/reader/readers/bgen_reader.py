# src/reader/readers/bgen_reader.py
"""BGEN reader.

BGEN stores genotype probabilities (P(AA), P(AB), P(BB)) per variant
per sample. The reader computes the expected ALT allele dosage:

    dosage = P(AB) + 2 * P(BB)

Layout:
    axis 0 = variant, axis 1 = sample.

Backed by bgen-reader, which supports BGEN 1.2 and 1.3.

Reference
---------
bgen-reader NumPy API:
https://bgen-reader.readthedocs.io/en/latest/numpyapi-api.html
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader


class BgenReader(Reader):
    """Reader for .bgen files."""

    extensions = [".bgen"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "BGEN reader expects dims as a two-element list, "
                "e.g. dims: [variant, sample]"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        try:
            from bgen_reader import open_bgen
        except ImportError as exc:
            raise ReaderError(
                "bgen-reader is required to read BGEN files. "
                "Install it with: pip install bgen-reader"
            ) from exc

        bgen = open_bgen(str(path), verbose=False)

        # probs: (n_samples, n_variants, 3)
        probs = bgen.read()
        n_samples, n_variants, _ = probs.shape

        # dosage = P(AB) + 2 * P(BB)
        data = (probs[:, :, 1] + 2.0 * probs[:, :, 2]).T
        data = data.astype(np.float32)

        # Missing: where all three probabilities are 0
        all_zero = (probs.sum(axis=2) == 0).T
        has_nan = np.isnan(probs).any(axis=2).T
        missing = all_zero | has_nan
        data[missing] = np.nan

        # Labels — bgen.ids and bgen.samples are numpy arrays
        variant_ids = [str(v) for v in bgen.ids]
        sample_ids = [str(s) for s in bgen.samples]

        if len(variant_ids) != n_variants:
            raise ReaderError(
                f"Variants table has {len(variant_ids)} rows but "
                f"data has {n_variants} variants"
            )
        if len(sample_ids) != n_samples:
            raise ReaderError(
                f"Samples table has {len(sample_ids)} rows but "
                f"data has {n_samples} samples"
            )

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(sample_ids)},
            },
            info={"missing_code": np.nan},
        )