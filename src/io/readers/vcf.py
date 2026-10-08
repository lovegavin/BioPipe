# src/io/readers/vcf.py
"""VCF reader.

Reads a VCF (optionally bgzipped) into ``GenotypeMatrix``,
``VariantTable`` and ``SampleTable``.

Conventions
-----------
* VCF column names follow the VCF specification and are not configurable.
* Only the GT field is interpreted. All other FORMAT fields are ignored.
* Dosage is the count of ALT alleles per genotype call, encoded as
  ``float32``. Missing calls use ``-1.0``.
* Ploidy is inferred from the first non-missing genotype call.
* ``allele_mode`` is set to ``"alt_dosage"``.
* Genome build is inferred from the header ``##reference`` line if
  possible; otherwise left as ``"unknown"``.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pysam

from src.core.forms import GenotypeMatrix, VariantTable, SampleTable

# Match common build identifiers in the header reference line.
_BUILD_PATTERNS = (
    (re.compile(r"GRCh38|hg38", re.IGNORECASE), "GRCh38"),
    (re.compile(r"GRCh37|hg19|b37", re.IGNORECASE), "GRCh37"),
)


def _infer_build(header) -> str:
    """Infer genome build from the ``##reference`` header line."""
    for rec in header.records:
        if rec.key == "reference":
            value = str(rec.value)
            for pattern, label in _BUILD_PATTERNS:
                if pattern.search(value):
                    return label
    return "unknown"


def read_vcf(path: str) -> dict:
    """Read a VCF file into memory forms.

    Parameters
    ----------
    path : str
        Path to ``.vcf`` or ``.vcf.gz``.

    Returns
    -------
    dict
        ``{"genotype": GenotypeMatrix,
           "variant_table": VariantTable,
           "sample_table": SampleTable}``
    """
    vcf = pysam.VariantFile(path)
    samples = list(vcf.header.samples)
    n_samples = len(samples)
    genome_build = _infer_build(vcf.header)

    dosage_rows: list[np.ndarray] = []
    chroms: list[str] = []
    positions: list[int] = []
    variant_ids: list[str] = []
    refs: list[str] = []
    alts: list[str] = []
    ploidy: int | None = None

    for rec in vcf:
        # Infer ploidy from the first non-missing genotype.
        if ploidy is None:
            for s in samples:
                gt = rec.samples[s]["GT"]
                if gt is not None and all(a is not None for a in gt):
                    ploidy = len(gt)
                    break

        row = np.full(n_samples, -1.0, dtype=np.float32)
        for i, s in enumerate(samples):
            gt = rec.samples[s]["GT"]
            if gt is None or any(a is None for a in gt):
                continue
            row[i] = float(sum(gt))
        dosage_rows.append(row)

        chroms.append(rec.chrom)
        positions.append(int(rec.pos))
        variant_ids.append(rec.id if rec.id else f"{rec.chrom}:{rec.pos}")
        refs.append(rec.ref or "N")
        alts.append(rec.alts[0] if rec.alts else "N")

    vcf.close()

    if ploidy is None:
        raise ValueError(f"Unable to infer ploidy from VCF: {path}")
    if not dosage_rows:
        raise ValueError(f"VCF contains no variant records: {path}")

    data = np.vstack(dosage_rows)
    variant_ids_arr = np.asarray(variant_ids)
    sample_ids_arr = np.asarray(samples)

    genotype = GenotypeMatrix(
        data=data,
        variant_ids=variant_ids_arr,
        sample_ids=sample_ids_arr,
        ploidy=int(ploidy),
        missing_code=-1.0,
        allele_mode="alt_dosage",
        genome_build=genome_build,
        source_format="vcf",
    )

    variant_data = pd.DataFrame(
        {
            "CHROM": chroms,
            "POS": positions,
            "REF": refs,
            "ALT": alts,
        },
        index=pd.Index(variant_ids, name="ID"),
    )
    variant_table = VariantTable(
        data=variant_data,
        genome_build=genome_build,
        source_format="vcf",
    )

    sample_data = pd.DataFrame(index=pd.Index(samples, name="sample_id"))
    sample_table = SampleTable(data=sample_data, source_format="vcf")

    # Validate before returning — never let a malformed form escape.
    genotype.validate()
    variant_table.validate()
    sample_table.validate()

    print(
        f"[vcf] loaded {genotype.n_snps} variants x "
        f"{genotype.n_samples} samples (ploidy={genotype.ploidy})"
    )

    return {
        "genotype": genotype,
        "variant_table": variant_table,
        "sample_table": sample_table,
    }