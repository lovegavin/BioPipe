# src/reader/readers/bgen_reader.py
"""BGEN reader.

BGEN stores genotype probabilities (P(AA), P(AB), P(BB)) per variant
per sample. This reader computes the expected ALT allele dosage:

    dosage = P(AB) + 2 * P(BB)

Layout:
    axis 0 = variant, axis 1 = sample.

Backed by bgen-reader, which supports BGEN 1.2 and 1.3 and handles
compression internally.

Label rules accepted:

    builtin           variant: ids from the BGEN
                      sample:  samples from the BGEN
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Reference
---------
BGEN specification:
https://www.well.ox.ac.uk/~gav/bgen_format/

Info fields set:

    missing_code      np.nan
    ploidy            2
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class BgenReader(Reader):
    """Reader for .bgen files."""

    extensions = [".bgen"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"BGEN reader requires exactly two dims, got {dims}"
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

        probs = bgen.read()
        n_samples, n_variants, _ = probs.shape

        data = (probs[:, :, 1] + 2.0 * probs[:, :, 2]).T.astype(np.float32)

        all_zero = (probs.sum(axis=2) == 0).T
        data[all_zero] = np.nan

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

        final = _resolve_labels(
            labels, variant_dim, sample_dim, variant_ids, sample_ids
        )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={"missing_code": np.nan, "ploidy": 2},
        )


def _resolve_labels(labels, variant_dim, sample_dim,
                    variant_ids, sample_ids):
    final: dict[str, dict[str, int]] = {}

    for dim_name, builtin in (
        (variant_dim, variant_ids),
        (sample_dim, sample_ids),
    ):
        rule = labels.get(dim_name, "builtin")

        if rule in (None, "builtin"):
            final[dim_name] = unique_labels(builtin, dim_name, "bgen")
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
                f"BGEN reader: unsupported label rule for "
                f"'{dim_name}': {rule!r}"
            )

    return final