# src/reader/readers/vcf_reader.py
"""VCF reader.

Parses the GT field into per-ALT allele counts. Multi-allelic records
are split into one output row per ALT. Missing alleles become NaN.

Backed by cyvcf2 (htslib). gzip / bgzip inputs are transparently
handled by cyvcf2 itself.

Output layout is the natural VCF order:
    axis 0 = variant, axis 1 = sample.
``dims`` names the two axes in that order.

All header meta-information is stored in ``info``.
Per-variant INFO fields are not interpreted.
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
        n_samples = len(samples)
        if n_samples == 0:
            raise ReaderError("VCF has no samples")

        header_meta = _parse_header(vcf)

        variant_ids: list[str] = []
        rows: list[np.ndarray] = []
        ploidy: int | None = None

        for variant in vcf:
            arr = variant.genotype.array()   # (n_samples, ploidy+1)
            alleles = arr[:, :-1]            # last column is phased flag
            if ploidy is None and alleles.shape[1] > 0:
                ploidy = int(alleles.shape[1])

            missing = (alleles == -1).any(axis=1)

            vid = variant.ID
            if not vid:
                vid = f"{variant.CHROM}:{variant.POS}"

            alts = variant.ALT or []
            if len(alts) == 0:
                # skip reference-only records
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

        info = {
            "missing_code": np.nan,
            "source_format": "vcf",
            "encoding": "alt_count",
            "ploidy": ploidy,
            **header_meta,
        }

        return Form(
            data=data,
            dims=[variant_dim, sample_dim],
            labels={
                variant_dim: {v: i for i, v in enumerate(variant_ids)},
                sample_dim: {s: i for i, s in enumerate(samples)},
            },
            info=info,
        )


# --------------------------------------------------------------------- #
# Header parsing via cyvcf2's structured iterator
# --------------------------------------------------------------------- #

def _parse_header(vcf: VCF) -> dict:
    meta = {
        "fileformat": None,
        "fileDate": None,
        "reference": None,
        "assembly": None,
        "phasing": None,
        "sources": [],
        "contigs": [],
        "formats": {},
        "infos": {},
        "filters": {},
        "alt_alleles": {},
        "extra": {},
    }

    for record in vcf.header_iter():
        try:
            h = record.info()
        except Exception:
            continue

        htype = h.get("HeaderType")

        if htype == "GENERIC":
            key = h.get("key") or h.get("ID")
            value = h.get("value")
            if key is None:
                continue
            if key in meta:
                meta[key] = value
            elif key == "source":
                meta["sources"].append(value)
            else:
                meta["extra"].setdefault(key, []).append(value)

        elif htype == "CONTIG":
            meta["contigs"].append(dict(h))

        elif htype == "INFO":
            meta["infos"][h.get("ID", "")] = dict(h)

        elif htype == "FORMAT":
            meta["formats"][h.get("ID", "")] = dict(h)

        elif htype == "FILTER":
            meta["filters"][h.get("ID", "")] = dict(h)

        elif htype == "ALT":
            meta["alt_alleles"][h.get("ID", "")] = dict(h)

        elif htype in ("STRUCTURED", "SAMPLE", "PEDIGREE"):
            meta["extra"].setdefault(htype, []).append(dict(h))

    return meta