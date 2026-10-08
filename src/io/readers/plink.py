# src/io/readers/plink.py
"""PLINK reader (bed / bim / fam trio).

Reads a PLINK 1.x binary genotype triplet into ``GenotypeMatrix``,
``VariantTable`` and ``SampleTable``.

Conventions
-----------
* The ``.bed`` / ``.bim`` / ``.fam`` files must share the same stem and
  live in the same directory.
* Only diploid data is supported.
* Dosage is the ALT allele count, where ALT = ``.bim`` column A1 and
  REF = ``.bim`` column A2. This matches PLINK's ``--recode vcf``
  convention.
* Missing calls are encoded as ``-1.0``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from bed_reader import open_bed

from src.core.forms import GenotypeMatrix, VariantTable, SampleTable

_BIM_COLUMNS = ["CHROM", "ID", "CM", "POS", "A1", "A2"]
_FAM_COLUMNS = ["FID", "IID", "PID", "MID", "SEX", "PHENO"]


def read_plink(path: str) -> dict:
    """Read a PLINK triplet into memory forms.

    Parameters
    ----------
    path : str
        Path to the ``.bed`` file. ``.bim`` and ``.fam`` must exist
        alongside it with the same stem.

    Returns
    -------
    dict
        ``{"genotype": GenotypeMatrix,
           "variant_table": VariantTable,
           "sample_table": SampleTable}``
    """
    bed_path = Path(path)
    bim_path = bed_path.with_suffix(".bim")
    fam_path = bed_path.with_suffix(".fam")

    for p in (bed_path, bim_path, fam_path):
        if not p.exists():
            raise FileNotFoundError(
                f"PLINK component missing: {p}\n"
                f"  Expected stem: {bed_path.with_suffix('')}"
            )

    # Read genotypes as (n_samples, n_snps), then transpose to
    # (n_snps, n_samples) to match GenotypeMatrix layout.
    bed = open_bed(str(bed_path))
    raw = bed.read(dtype="float32")
    data = np.where(np.isnan(raw), -1.0, raw).astype(np.float32).T

    bim = pd.read_csv(
        bim_path, sep=r"\s+", header=None, dtype=str, names=_BIM_COLUMNS
    )
    variant_data = pd.DataFrame(
        {
            "CHROM": bim["CHROM"].astype(str).values,
            "POS": bim["POS"].astype(np.int64).values,
            "REF": bim["A2"].astype(str).values,   # A2 -> REF
            "ALT": bim["A1"].astype(str).values,   # A1 -> ALT
        },
        index=pd.Index(bim["ID"].astype(str).values, name="ID"),
    )

    fam = pd.read_csv(
        fam_path, sep=r"\s+", header=None, dtype=str, names=_FAM_COLUMNS
    )
    sample_data = pd.DataFrame(
        {"FID": fam["FID"].astype(str).values},
        index=pd.Index(fam["IID"].astype(str).values, name="sample_id"),
    )

    genotype = GenotypeMatrix(
        data=data,
        variant_ids=variant_data.index.to_numpy(),
        sample_ids=sample_data.index.to_numpy(),
        ploidy=2,
        missing_code=-1.0,
        allele_mode="alt_dosage",
        genome_build="unknown",
        source_format="plink",
    )
    variant_table = VariantTable(
        data=variant_data, genome_build="unknown", source_format="plink"
    )
    sample_table = SampleTable(data=sample_data, source_format="plink")

    genotype.validate()
    variant_table.validate()
    sample_table.validate()

    print(
        f"[plink] loaded {genotype.n_snps} variants x "
        f"{genotype.n_samples} samples (ploidy=2)"
    )

    return {
        "genotype": genotype,
        "variant_table": variant_table,
        "sample_table": sample_table,
    }