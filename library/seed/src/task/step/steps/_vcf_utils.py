"""Dependency-free VCF/VCF.gz helpers shared by the vcf_* operators.

The helpers deliberately avoid pysam/cyvcf2 so the operators run in the base
environment.  They stream text, keep memory bounded by one record, and expose
only the pieces the operators need: the header, site-level columns, INFO and
lazy genotype access.
"""
from __future__ import annotations

import gzip
import io
from pathlib import Path


def open_text(path):
    """Open a plain or gzip-compressed VCF as UTF-8 text."""
    text = str(path)
    if text.endswith(".gz"):
        return gzip.open(text, "rt", encoding="utf-8", errors="replace")
    return open(text, "rt", encoding="utf-8", errors="replace")


def read_header(stream):
    """Return (meta_lines, format_columns, samples) and leave stream at data."""
    meta = []
    for line in stream:
        if line.startswith("##"):
            meta.append(line.rstrip("\n"))
            continue
        if line.startswith("#CHROM"):
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 8:
                raise ValueError("VCF #CHROM line has fewer than 8 columns")
            return meta, columns[8:], columns[9:]
        raise ValueError("VCF header must contain ## meta lines then #CHROM")
    raise ValueError("VCF header is incomplete (no #CHROM line)")


def iter_sites(stream):
    """Yield (fixed, rest) per record without splitting the genotype blob.

    fixed is the list of the 8 mandatory columns (CHROM..INFO); rest is the
    raw text after INFO (FORMAT + samples) or "" for sites-only VCFs.
    """
    for line in stream:
        if not line or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t", 8)
        if len(parts) < 8:
            raise ValueError("VCF record has fewer than 8 columns")
        rest = parts[8] if len(parts) > 8 else ""
        yield parts[:8], rest


def iter_records(stream):
    """Yield the full tab-split record (all genotype columns)."""
    for line in stream:
        if not line or line.startswith("#"):
            continue
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 8:
            raise ValueError("VCF record has fewer than 8 columns")
        yield parts


def parse_info(text):
    """Parse an INFO string into {key: value}; flags map to True."""
    info = {}
    if not text or text == ".":
        return info
    for item in text.split(";"):
        if not item:
            continue
        key, sep, value = item.partition("=")
        info[key] = value if sep else True
    return info


def parse_qual(text):
    """Return QUAL as float, or None for a missing ('.') value."""
    if text in ("", "."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def alt_alleles(text):
    if text in ("", "."):
        return []
    return text.split(",")


def genotype_dosage(gt, allele_index=1):
    """Alt-allele dosage for one GT string.

    Returns 0/1/2 (or more for multiallelic), or None when the genotype is
    missing or partially missing.  Haploid calls are counted as their dosage.
    """
    if not gt or gt == ".":
        return None
    alleles = gt.replace("|", "/").split("/")
    dosage = 0
    for allele in alleles:
        if allele == ".":
            return None
        if allele == str(allele_index):
            dosage += 1
    return dosage


def allele_count(gt):
    """Number of called alleles (1 for haploid, 2 for diploid)."""
    if not gt or gt == ".":
        return 0
    return len(gt.replace("|", "/").split("/"))


def chrom_key(chrom):
    """Normalise a contig name for cross-file matching (chr22 == 22)."""
    text = str(chrom).strip()
    if text.lower().startswith("chr"):
        text = text[3:]
    return text


def region_match(chrom, pos, region):
    """True when a site falls inside a 'chr', 'chr:start-end' region."""
    if not region:
        return True
    text = str(region).strip()
    if ":" not in text:
        return chrom_key(chrom) == chrom_key(text)
    contig, _, span = text.partition(":")
    if chrom_key(chrom) != chrom_key(contig):
        return False
    start_text, _, end_text = span.partition("-")
    try:
        start = int(start_text) if start_text else 1
        end = int(end_text) if end_text else 2**62
    except ValueError:
        return False
    return start <= int(pos) <= end


def sample_indices(samples, wanted):
    """Map requested sample names to column indices (empty list = all)."""
    if not wanted:
        return list(range(len(samples)))
    lookup = {name: index for index, name in enumerate(samples)}
    missing = [name for name in wanted if name not in lookup]
    if missing:
        raise ValueError("VCF has no sample(s): " + ", ".join(missing))
    return [lookup[name] for name in wanted]


def split_samples(rest, indices):
    """Split a genotype blob and return only the requested sample fields."""
    fields = rest.split("\t")
    return [fields[index] for index in indices]


def af_from_info(info):
    """Best-effort alternate allele frequency from INFO (AF or AC/AN)."""
    if "AF" in info and info["AF"] not in (True, "."):
        try:
            return float(str(info["AF"]).split(",")[0])
        except ValueError:
            return None
    if "AC" in info and "AN" in info:
        try:
            ac = float(str(info["AC"]).split(",")[0])
            an = float(info["AN"])
            return ac / an if an else None
        except (TypeError, ValueError):
            return None
    return None
