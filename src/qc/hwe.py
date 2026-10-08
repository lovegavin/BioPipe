# src/qc/hwe.py
"""Hardy-Weinberg equilibrium exact test (Wigginton et al. 2005).

Reference
---------
Wigginton JE, Cutler DJ, Abecasis GR (2005).
A note on exact tests of Hardy-Weinberg equilibrium.
Am J Hum Genet 76(5):887-93.
"""

from __future__ import annotations

import numpy as np


def hwe_exact_test(n_hom_ref: int, n_het: int, n_hom_alt: int) -> float:
    """Exact HWE test for diploid genotype counts.

    Parameters
    ----------
    n_hom_ref, n_het, n_hom_alt : int
        Observed counts of the three diploid genotypes.

    Returns
    -------
    float
        Two-sided p-value in ``[0, 1]``.
    """
    if n_het > n_hom_ref + n_hom_alt:
        n_hom_ref, n_hom_alt = n_hom_alt, n_hom_ref

    homc = min(n_hom_ref, n_hom_alt)
    homr = max(n_hom_ref, n_hom_alt)
    rare = 2 * homc + n_het
    genotypes = n_het + homr + homc

    if genotypes == 0:
        return 1.0

    probs = np.zeros(rare + 1, dtype=float)
    mid = rare * (2 * genotypes - rare) // (2 * genotypes)
    if mid % 2 != rare % 2:
        mid += 1
    probs[mid] = 1.0

    # Recurrence downward.
    curr_hets, curr_homr, curr_homc = mid, (rare - mid) // 2, 0
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets > 1:
        probs[curr_hets - 2] = (
            probs[curr_hets] * curr_hets * (curr_hets - 1)
            / (4.0 * (curr_homr + 1) * (curr_homc + 1))
        )
        curr_homr += 1
        curr_homc += 1
        curr_hets -= 2

    # Recurrence upward.
    curr_hets, curr_homr = mid, (rare - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets <= rare - 2:
        probs[curr_hets + 2] = (
            probs[curr_hets] * 4.0 * curr_homr * curr_homc
            / ((curr_hets + 2) * (curr_hets + 1))
        )
        curr_homr -= 1
        curr_homc -= 1
        curr_hets += 2

    total = probs.sum()
    if total <= 0:
        return 1.0
    probs /= total
    return float(min(max(probs[probs <= probs[n_het]].sum(), 0.0), 1.0))


def compute_hwe_pvalues(
    data: np.ndarray,
    phenotype_values: np.ndarray | None = None,
    missing_code: float = -1.0,
) -> tuple[np.ndarray, str]:
    """Compute HWE p-values per variant.

    If ``phenotype_values`` is binary, the test is restricted to
    controls (value 0). Otherwise all samples are used.

    Returns
    -------
    (pvalues, scope)
        ``scope`` is ``"controls_only"`` or ``"all_samples"``.
    """
    n_snps, n_samples = data.shape
    pvals = np.full(n_snps, np.nan, dtype=float)

    if phenotype_values is not None and len(np.unique(phenotype_values)) == 2:
        ctrl_mask = phenotype_values == 0
        scope = "controls_only" if ctrl_mask.sum() >= 10 else "all_samples"
    else:
        ctrl_mask = np.ones(n_samples, dtype=bool)
        scope = "all_samples"

    for j in range(n_snps):
        col = data[j][ctrl_mask]
        valid = col[col != missing_code]
        if valid.size < 3:
            continue
        n_aa = int(np.sum(valid == 0))
        n_ab = int(np.sum(valid == 1))
        n_bb = int(np.sum(valid == 2))
        pvals[j] = hwe_exact_test(n_aa, n_ab, n_bb)

    return pvals, scope