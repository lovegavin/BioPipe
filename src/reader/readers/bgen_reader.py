# src/reader/readers/bgen_reader.py
"""BGEN reader for biallelic diploid files.

BGEN stores genotype probabilities P(AA), P(AB), P(BB) per variant
per sample. This reader computes the expected ALT allele dosage:

    dosage = P(AB) + 2 * P(BB)

Layout:
    axis 0 = variant, axis 1 = sample.

Scope
-----
This reader handles biallelic diploid BGEN files only.

Two common non-compliant cases raise an explicit ``ReaderError``
instead of silently producing wrong data:

* Non-diploid data (haplotypes, haploids) — the sum of the three
  genotype probabilities is not 2 for at least one variant.
* Complex data (per-variant allele count or ploidy variation) —
  ``bgen_reader`` cannot unify the genotypes into a single tensor,
  or the tensor does not have exactly 3 genotype columns per
  variant.

Label rules accepted:

    builtin           variant: ids from the BGEN
                      sample:  samples from the BGEN
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set:

    missing_code      np.nan
    ploidy            2
    representation    "dosage"

Reference
---------
BGEN specification: https://www.well.ox.ac.uk/~gav/bgen_format/
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.core.contracts import reader_contract
from src.reader.readers._labels import unique_labels


class BgenReader(Reader):
    """Reader for biallelic diploid .bgen files."""
    dependencies = ['bgen-reader>=4.0']
    dependency_imports = ['bgen_reader']

    output_contract = reader_contract(representation="dosage", ploidy=2)

    file_input = {'dims': ['variant', 'sample'], 'labels': {'variant': 'builtin', 'sample': 'builtin'}}

    extensions = [".bgen"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


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

        try:
            with open_bgen(str(path), verbose=False, allow_complex=False) as bgen:
                probs = bgen.read()
                variant_ids = [str(v) for v in bgen.ids]
                sample_ids = [str(s) for s in bgen.samples]
                chromosomes = [str(v) for v in bgen.chromosomes]
                positions = [int(v) for v in bgen.positions]
        except ValueError as exc:
            if "allow_complex is False" in str(exc):
                raise ReaderError(
                    "BGEN reader: complex BGEN files (per-variant "
                    "ploidy or allele-count variation) are not "
                    "supported. This reader handles biallelic diploid "
                    "data only."
                ) from exc
            raise

        n_samples, n_variants, n_allele_cols = probs.shape

        if n_allele_cols != 3:
            raise ReaderError(
                f"BGEN reader: expected 3 genotype columns for a "
                f"biallelic diploid variant, got {n_allele_cols}. "
                f"This reader handles biallelic diploid data only; "
                f"multi-allelic or non-diploid BGEN files must be "
                f"converted to VCF and read via the VCF reader."
            )

        # For a diploid genotype P(AA), P(AB), P(BB) form a
        # probability distribution: row_sums == 1.0 for every
        # well-formed variant, including monomorphic ones where
        # P(AA) = 1 and the other two are 0. Anything else means
        # the file is not biallelic diploid.
        row_sums = probs.sum(axis=2)
        nonzero = row_sums > 0
        if nonzero.any():
            with np.errstate(invalid="ignore"):
                bad = nonzero & (np.abs(row_sums - 1.0) > 0.01)
            if bad.any():
                worst = float(np.nanmax(row_sums[bad]))
                raise ReaderError(
                    f"BGEN reader: expected a diploid genotype "
                    f"probability distribution (sum over the 3 "
                    f"genotype columns equals 1) but found rows with "
                    f"sum up to {worst:.2f}. This reader handles "
                    f"biallelic diploid BGEN files only."
                )

        data = (probs[:, :, 1] + 2.0 * probs[:, :, 2]).T.astype(np.float32)

        all_zero = row_sums.T == 0
        data[all_zero] = np.nan

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
        if len(chromosomes) != n_variants or len(positions) != n_variants:
            raise ReaderError(
                "BGEN reader: chromosome/position metadata length "
                "does not match the variant count"
            )

        final = _resolve_labels(
            labels, variant_dim, sample_dim, variant_ids, sample_ids
        )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "ploidy": 2,
                "representation": "dosage",
                "chrom": chromosomes,
                "pos": positions,
            },
            axis_info={variant_dim: ["chrom", "pos"]},
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
