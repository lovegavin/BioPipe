# src/reader/readers/vcf_reader.py
"""VCF reader.

Parses the GT field into per-ALT allele counts. Multi-allelic records
are split into one output row per ALT. Missing alleles become NaN.

Backed by cyvcf2 (htslib). Compressed input (.vcf.gz) is handled
directly; this reader receives the original path.

Layout
------
    axis 0 = variant, axis 1 = sample.

The VCF record layout is fixed by the specification:

    #CHROM  POS  ID  REF  ALT  QUAL  FILTER  INFO  FORMAT  sample1...

Only ``GT`` is consumed from the FORMAT column. All other per-sample
fields are ignored.

Variant ID policy
-----------------
    ID present, single ALT   use the ID as-is
    ID present, multi ALT    ``{id}:{alt}`` per split row
    ID missing               ``{CHROM}:{POS}:{ALT}`` per split row

Sample identifiers come from the #CHROM header line.

Label rules accepted
--------------------
    builtin           variant: derived IDs (above)
                      sample:  header sample names
    auto              position indices ``"0"``, ``"1"``, ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>`` (see ``_labels.py``).

Info fields set
---------------
    missing_code      ``np.nan``
    ploidy            inferred from the first non-missing GT
    chrom             ``list[str]``, length = number of variant rows
    pos               ``list[int]``, length = number of variant rows

The ``chrom`` and ``pos`` arrays are parallel to the variant axis and
are kept in sync when the axis is subset (see ``Form.subset_axis``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from cyvcf2 import VCF

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class VcfReader(Reader):
    """Reader for .vcf and .vcf.gz files."""

    extensions = [".vcf"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"VCF reader requires exactly two dims, got {dims}"
            )
        variant_dim, sample_dim = dims[0], dims[1]

        vcf = VCF(str(path))
        samples = list(vcf.samples)
        if not samples:
            raise ReaderError("VCF has no samples")

        variant_ids: list[str] = []
        chroms: list[str] = []
        positions: list[int] = []
        rows: list[np.ndarray] = []
        ploidy: int | None = None

        for variant in vcf:
            arr = variant.genotype.array()
            alleles = arr[:, :-1]
            if ploidy is None and alleles.shape[1] > 0:
                ploidy = int(alleles.shape[1])
            missing = (alleles == -1).any(axis=1)

            alts = variant.ALT or []
            if not alts:
                continue

            vid_raw = variant.ID or ""
            has_real_id = vid_raw not in ("", ".")

            if has_real_id:
                if len(alts) == 1:
                    counts = (alleles == 1).sum(axis=1).astype(np.float32)
                    counts[missing] = np.nan
                    variant_ids.append(vid_raw)
                    chroms.append(str(variant.CHROM))
                    positions.append(int(variant.POS))
                    rows.append(counts)
                else:
                    for k, alt in enumerate(alts, start=1):
                        counts = (alleles == k).sum(axis=1).astype(np.float32)
                        counts[missing] = np.nan
                        variant_ids.append(f"{vid_raw}:{alt}")
                        chroms.append(str(variant.CHROM))
                        positions.append(int(variant.POS))
                        rows.append(counts)
            else:
                base = f"{variant.CHROM}:{variant.POS}"
                for k, alt in enumerate(alts, start=1):
                    counts = (alleles == k).sum(axis=1).astype(np.float32)
                    counts[missing] = np.nan
                    variant_ids.append(f"{base}:{alt}")
                    chroms.append(str(variant.CHROM))
                    positions.append(int(variant.POS))
                    rows.append(counts)

        vcf.close()

        if not rows:
            raise ReaderError("VCF has no variant records")
        if ploidy is None:
            raise ReaderError("VCF has no valid GT calls")

        data = np.stack(rows, axis=0).astype(np.float32)

        final: dict[str, dict[str, int]] = {}

        variant_rule = labels.get(variant_dim, "builtin")
        if variant_rule in (None, "builtin"):
            final[variant_dim] = unique_labels(
                variant_ids, variant_dim, "vcf"
            )
        elif variant_rule == "auto":
            final[variant_dim] = {
                str(i): i for i in range(len(variant_ids))
            }
        elif isinstance(variant_rule, dict):
            final[variant_dim] = {
                str(k): int(v) for k, v in variant_rule.items()
            }
        else:
            raise ReaderError(
                f"VCF reader: unsupported label rule for "
                f"'{variant_dim}': {variant_rule!r}"
            )

        sample_rule = labels.get(sample_dim, "builtin")
        if sample_rule in (None, "builtin"):
            final[sample_dim] = unique_labels(
                samples, sample_dim, "vcf"
            )
        elif sample_rule == "auto":
            final[sample_dim] = {
                str(i): i for i in range(len(samples))
            }
        elif isinstance(sample_rule, dict):
            final[sample_dim] = {
                str(k): int(v) for k, v in sample_rule.items()
            }
        else:
            raise ReaderError(
                f"VCF reader: unsupported label rule for "
                f"'{sample_dim}': {sample_rule!r}"
            )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "ploidy": ploidy,
                "chrom": chroms,
                "pos": positions,
            },
            axis_info={variant_dim: ["chrom", "pos"]},
        )