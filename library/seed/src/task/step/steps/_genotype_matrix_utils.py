"""Shared genotype-matrix helpers for the population-structure operators.

The input is a VCF/VCF.gz file artifact.  Genotypes are decoded to ALT allele
counts (0/1/2); a missing or non-biallelic call becomes NaN.  The matrix is
standardised per variant as ``(g - 2p) / sqrt(2p(1-p))`` with missing calls
mean-imputed to zero, and the genetic relationship matrix is
``Z.T @ Z / M`` where ``M`` is the number of biallelic SNP records scanned
(monomorphic variants contribute zero).  This matches PLINK 2's
``--make-rel``/``--pca`` scaling, so both tools can be compared value by value.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError

from . import _vcf_utils as vcf


_BASES = frozenset("ACGT")


def _allele_count(gt: str) -> float:
    if not gt:
        return np.nan
    alleles = gt.replace("|", "/").split("/")
    total = 0.0
    for allele in alleles:
        if allele == ".":
            return np.nan
        if allele == "1":
            total += 1.0
        elif allele != "0":
            return np.nan
    return total


def load_genotypes(path, max_variants: int = 0):
    """Return (samples, variant_ids, genotype matrix [variant, sample])."""
    samples: list[str] = []
    variants: list[str] = []
    rows: list[np.ndarray] = []
    with vcf.open_text(path) as stream:
        _meta, _columns, header_samples = vcf.read_header(stream)
        samples = [str(name) for name in header_samples]
        if not samples:
            raise StepError("genotype matrix: the VCF has no sample columns")
        for parts in vcf.iter_records(stream):
            chrom, pos, ref, alt = parts[0], parts[1], parts[3], parts[4]
            if len(ref) != 1 or len(alt) != 1 or ref not in _BASES or alt not in _BASES:
                continue
            if len(parts) < 10:
                raise StepError("genotype matrix: the VCF has no genotype columns")
            fields = parts[8].split(":")
            if "GT" not in fields:
                raise StepError("genotype matrix: FORMAT does not contain GT")
            gt_index = fields.index("GT")
            row = np.empty(len(samples), dtype=np.float64)
            for index, cell in enumerate(parts[9:]):
                values = cell.split(":")
                if gt_index >= len(values):
                    row[index] = np.nan
                else:
                    row[index] = _allele_count(values[gt_index])
            variants.append(f"{chrom}:{pos}:{ref}:{alt}")
            rows.append(row)
            if max_variants and len(rows) >= max_variants:
                break
    if not variants:
        raise StepError("genotype matrix: no biallelic SNP records were found")
    return samples, variants, np.vstack(rows)


def standardise(genotypes: np.ndarray, maf: float = 0.0):
    """Return (standardised matrix, used variant indices, allele frequencies)."""
    if maf < 0 or maf > 0.5:
        raise StepError("genotype matrix: maf must be within [0, 0.5]")
    called = np.sum(~np.isnan(genotypes), axis=1)
    if np.any(called == 0):
        raise StepError("genotype matrix: every variant needs a called genotype")
    allele_counts = np.nansum(genotypes, axis=1)
    frequency = allele_counts / (2.0 * called)
    with np.errstate(invalid="ignore", divide="ignore"):
        usable = (frequency > 0) & (frequency < 1)
        usable &= np.minimum(frequency, 1.0 - frequency) >= maf
    used = np.where(usable)[0]
    if used.size == 0:
        raise StepError("genotype matrix: no variant passed the MAF filter")

    matrix = np.zeros_like(genotypes, dtype=np.float64)
    sub = genotypes[used]
    p = frequency[used]
    centred = np.where(np.isnan(sub), 0.0, sub - 2.0 * p[:, None])
    matrix[used] = centred / np.sqrt(2.0 * p * (1.0 - p))[:, None]
    return matrix, used, frequency


def relationship_matrix(matrix: np.ndarray) -> np.ndarray:
    """GRM = Z.T @ Z / M, with M the full biallelic SNP count."""
    total = matrix.shape[0]
    if total == 0:
        raise StepError("genotype matrix: no variants are available")
    return (matrix.T @ matrix) / float(total)


def pca_decomposition(grm: np.ndarray, n_components: int):
    """Return (eigenvalues, eigenvectors) sorted by decreasing eigenvalue."""
    if n_components < 1:
        raise StepError("genotype matrix: n_components must be a positive integer")
    values, vectors = np.linalg.eigh(grm)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    take = min(int(n_components), values.size)
    return values[:take], vectors[:, :take]


def component_labels(count: int):
    return [f"PC{index + 1}" for index in range(count)]
