# src/reader/readers/vcf_reader.py
"""VCF reader.

Parses the GT field into per-ALT allele counts. Multi-allelic records
are split into one output row per ALT. Missing alleles become NaN.

Backend selection
-----------------
On Linux/macOS this uses cyvcf2 (htslib), which is fast.
On Windows, cyvcf2/htslib is experimental and crashes the interpreter
with STATUS_HEAP_CORRUPTION (0xC0000374) on many real VCFs. There we
fall back to a pure Python parser. Same input, same output.

Layout
------
    axis 0 = variant, axis 1 = sample.

Variant ID policy
-----------------
    ID present, single ALT   use the ID as-is
    ID present, multi ALT    ``{id}:{alt}`` per split row
    ID missing               ``{CHROM}:{POS}:{ALT}`` per split row

Info fields set
---------------
    missing_code      ``np.nan``
    ploidy            inferred from the first non-missing GT
    chrom             ``list[str]``, length = number of variant rows
    pos               ``list[int]``, length = number of variant rows
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.core.contracts import reader_contract
from src.reader.readers._labels import unique_labels


def _parse_gt(gt_str: str) -> list[int]:
    """Return allele indices for one sample; -1 means missing."""
    if not gt_str or gt_str == ".":
        return [-1]
    parts = gt_str.replace("|", "/").split("/")
    out = []
    for p in parts:
        if p in (".", ""):
            out.append(-1)
        else:
            try:
                out.append(int(p))
            except ValueError:
                out.append(-1)
    return out


def _iter_vcf(path: Path):
    """Yield (chrom, pos, id, alts, sample_alleles) for each record.

    Pure Python; gzip is transparent. sample_alleles is a list of
    allele-index lists, one per sample, in header order.
    """
    import gzip

    opener = gzip.open if Path(path).suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        samples: list[str] = []
        for line in f:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                header = line.rstrip("\n").split("\t")
                samples = header[9:]
                break
        else:
            raise ReaderError("VCF header (#CHROM) is missing")
        if not samples:
            raise ReaderError("VCF has no samples")

        for line in f:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 + len(samples):
                raise ReaderError("VCF record sample count does not match the #CHROM header")
            chrom = fields[0]
            try:
                pos = int(fields[1])
            except ValueError as exc:
                raise ReaderError(f"Invalid VCF position: {fields[1]!r}") from exc
            vid = fields[2]
            alt_field = fields[4]
            alts = [] if alt_field in (".", "") else alt_field.split(",")

            fmt_keys = fields[8].split(":") if fields[8] else []
            try:
                gt_idx = fmt_keys.index("GT")
            except ValueError:
                gt_idx = -1

            sample_alleles = []
            for cell in fields[9:]:
                if gt_idx < 0:
                    sample_alleles.append([-1])
                    continue
                parts = cell.split(":")
                if gt_idx >= len(parts):
                    sample_alleles.append([-1])
                    continue
                sample_alleles.append(_parse_gt(parts[gt_idx]))
            yield chrom, pos, vid, alts, sample_alleles, samples


def _read_pure_python(path: Path):
    """Pure Python read. Returns the same tuple shape the cyvcf2 path builds."""
    variant_ids: list[str] = []
    chroms: list[str] = []
    positions: list[int] = []
    rows: list[np.ndarray] = []
    ploidy: int | None = None
    samples: list[str] = []

    for chrom, pos, vid, alts, sample_alleles, samples in _iter_vcf(path):
        if not alts:
            continue
        # A bare '.' has no implied ploidy. Infer it only from calls with at
        # least one observed allele; do not turn ragged missing calls into a
        # rectangular NumPy array or mistake them for haploid genotypes.
        for alleles in sample_alleles:
            if any(a < -1 or a > len(alts) for a in alleles):
                raise ReaderError("VCF GT allele index is outside the REF/ALT range")
            if any(a >= 0 for a in alleles):
                if ploidy is None:
                    ploidy = len(alleles)
                if len(alleles) != ploidy:
                    raise ReaderError(
                        "VCF contains mixed ploidy; a single info.ploidy cannot describe these calls"
                    )
        missing = np.array([any(a == -1 for a in call) for call in sample_alleles])

        def alt_counts(allele):
            counts = np.array([call.count(allele) for call in sample_alleles], dtype=np.float32)
            counts[missing] = np.nan
            return counts
        has_real_id = vid not in ("", ".")

        if has_real_id and len(alts) == 1:
            counts = alt_counts(1)
            variant_ids.append(vid)
            chroms.append(chrom)
            positions.append(pos)
            rows.append(counts)
        else:
            base = vid if has_real_id else f"{chrom}:{pos}"
            for k, alt in enumerate(alts, start=1):
                counts = alt_counts(k)
                variant_ids.append(f"{base}:{alt}" if has_real_id else f"{base}:{alt}")
                chroms.append(chrom)
                positions.append(pos)
                rows.append(counts)

    return variant_ids, samples, chroms, positions, rows, ploidy


def _read_cyvcf2(path: Path):
    """cyvcf2 path. Only used on non-Windows platforms."""
    from cyvcf2 import VCF

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
        if alleles.shape[1] != ploidy or (alleles < -1).any():
            vcf.close()
            raise ReaderError(
                "VCF contains mixed ploidy; a single info.ploidy cannot describe these calls"
            )
        missing = (alleles == -1).any(axis=1)
        alts = variant.ALT or []
        if not alts:
            continue
        vid_raw = variant.ID or ""
        has_real_id = vid_raw not in ("", ".")
        if has_real_id and len(alts) == 1:
            counts = (alleles == 1).sum(axis=1).astype(np.float32)
            counts[missing] = np.nan
            variant_ids.append(vid_raw)
            chroms.append(str(variant.CHROM))
            positions.append(int(variant.POS))
            rows.append(counts)
        else:
            base = vid_raw if has_real_id else f"{variant.CHROM}:{variant.POS}"
            for k, alt in enumerate(alts, start=1):
                counts = (alleles == k).sum(axis=1).astype(np.float32)
                counts[missing] = np.nan
                variant_ids.append(f"{base}:{alt}" if has_real_id else f"{base}:{alt}")
                chroms.append(str(variant.CHROM))
                positions.append(int(variant.POS))
                rows.append(counts)
    vcf.close()
    return variant_ids, samples, chroms, positions, rows, ploidy


class VcfReader(Reader):
    """Reader for .vcf and .vcf.gz files."""

    output_contract = reader_contract(representation="hard_call", coordinates=True)

    file_input = {
        "dims": ["variant", "sample"],
        "labels": {"variant": "builtin", "sample": "builtin"},
        "compression": [".gz"],
    }

    extensions = [".vcf"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"VCF reader requires exactly two dims, got {dims}")
        variant_dim, sample_dim = dims[0], dims[1]

        # Windows: cyvcf2/htslib crashes natively. Always use pure Python there.
        if os.name == "nt":
            variant_ids, samples, chroms, positions, rows, ploidy = _read_pure_python(path)
        else:
            try:
                variant_ids, samples, chroms, positions, rows, ploidy = _read_cyvcf2(path)
            except ImportError:
                variant_ids, samples, chroms, positions, rows, ploidy = _read_pure_python(path)

        if not rows:
            raise ReaderError("VCF has no variant records")
        if ploidy is None:
            raise ReaderError("VCF has no valid GT calls")

        data = np.stack(rows, axis=0).astype(np.float32)

        final: dict[str, dict[str, int]] = {}

        variant_rule = labels.get(variant_dim, "builtin")
        if variant_rule in (None, "builtin"):
            final[variant_dim] = unique_labels(variant_ids, variant_dim, "vcf")
        elif variant_rule == "auto":
            final[variant_dim] = {str(i): i for i in range(len(variant_ids))}
        elif isinstance(variant_rule, dict):
            final[variant_dim] = {str(k): int(v) for k, v in variant_rule.items()}
        else:
            raise ReaderError(
                f"VCF reader: unsupported label rule for '{variant_dim}': {variant_rule!r}"
            )

        sample_rule = labels.get(sample_dim, "builtin")
        if sample_rule in (None, "builtin"):
            final[sample_dim] = unique_labels(samples, sample_dim, "vcf")
        elif sample_rule == "auto":
            final[sample_dim] = {str(i): i for i in range(len(samples))}
        elif isinstance(sample_rule, dict):
            final[sample_dim] = {str(k): int(v) for k, v in sample_rule.items()}
        else:
            raise ReaderError(
                f"VCF reader: unsupported label rule for '{sample_dim}': {sample_rule!r}"
            )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "representation": "hard_call",
                "ploidy": ploidy,
                "chrom": chroms,
                "pos": positions,
            },
            axis_info={variant_dim: ["chrom", "pos"]},
        )
