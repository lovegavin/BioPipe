# src/core/forms/genotype.py
"""GenotypeMatrix — the canonical genotype dosage representation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.core.errors import ValidationError


@dataclass
class GenotypeMatrix:
    """Site-by-sample genotype dosage matrix.

    Parameters
    ----------
    data : np.ndarray
        Shape ``(n_snps, n_samples)``, dtype ``float32``.
        Missing values are encoded as ``missing_code`` (default ``-1.0``).
    variant_ids : np.ndarray
        Shape ``(n_snps,)``. Unique variant identifiers.
    sample_ids : np.ndarray
        Shape ``(n_samples,)``. Unique sample identifiers.
    ploidy : int
        Number of allele copies per genotype call.
    missing_code : float, optional
        Sentinel value used for missing calls. Default ``-1.0``.
    allele_mode : str, optional
        Semantics of the dosage value:

        * ``"alt_dosage"`` — value equals the count of ALT alleles.
        * ``"ref_dosage"`` — value equals the count of REF alleles.
    genome_build : str, optional
        Reference genome build. One of ``"GRCh37"``, ``"GRCh38"``,
        ``"unknown"``.
    source_format : str, optional
        Reader that produced this form.
    backend : str, optional
        Array backend. ``"numpy"`` for now.
    """

    data: np.ndarray
    variant_ids: np.ndarray
    sample_ids: np.ndarray
    ploidy: int
    missing_code: float = -1.0
    allele_mode: str = "alt_dosage"
    genome_build: str = "unknown"
    source_format: str = "unknown"
    backend: str = "numpy"

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def n_snps(self) -> int:
        return int(self.data.shape[0])

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[1])

    # ------------------------------------------------------------------ #
    # Sample-indexed protocol
    # ------------------------------------------------------------------ #

    def subset_samples(self, ids) -> "GenotypeMatrix":
        """Return a new matrix restricted to (and reordered by) sample IDs.

        Parameters
        ----------
        ids : sequence of str
            Sample identifiers to retain, in the desired output order.
            Every ID must exist in ``self.sample_ids``.
        """
        ids = [str(s) for s in ids]
        position = {s: i for i, s in enumerate(self.sample_ids.tolist())}

        missing = [s for s in ids if s not in position]
        if missing:
            preview = ", ".join(missing[:5])
            more = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise KeyError(
                f"GenotypeMatrix.subset_samples: unknown sample IDs: "
                f"{preview}{more}"
            )

        col_idx = np.asarray([position[s] for s in ids], dtype=int)

        return GenotypeMatrix(
            data=self.data[:, col_idx].copy(),
            variant_ids=self.variant_ids.copy(),
            sample_ids=np.asarray(ids),
            ploidy=self.ploidy,
            missing_code=self.missing_code,
            allele_mode=self.allele_mode,
            genome_build=self.genome_build,
            source_format=self.source_format,
            backend=self.backend,
        )

    # ------------------------------------------------------------------ #
    # Variant subsetting (not part of the SampleIndexed protocol)
    # ------------------------------------------------------------------ #

    def subset_snps(self, mask) -> "GenotypeMatrix":
        """Return a new matrix restricted to variants selected by ``mask``.

        Accepts a boolean mask of length ``n_snps`` or positional row
        indices.
        """
        mask = np.asarray(mask)

        if mask.dtype == bool:
            if mask.shape[0] != self.n_snps:
                raise ValidationError(
                    "GenotypeMatrix",
                    "boolean mask length mismatch",
                    f"mask={mask.shape[0]} snps={self.n_snps}",
                )
            new_data = self.data[mask]
            new_ids = self.variant_ids[mask]
        else:
            new_data = self.data[mask]
            new_ids = self.variant_ids[mask]

        return GenotypeMatrix(
            data=new_data.copy(),
            variant_ids=new_ids.copy(),
            sample_ids=self.sample_ids.copy(),
            ploidy=self.ploidy,
            missing_code=self.missing_code,
            allele_mode=self.allele_mode,
            genome_build=self.genome_build,
            source_format=self.source_format,
            backend=self.backend,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if self.data.ndim != 2:
            raise ValidationError(
                "GenotypeMatrix",
                "data must be 2-dimensional",
                f"ndim={self.data.ndim}",
            )

        n_snps, n_samples = self.data.shape

        if self.variant_ids.shape[0] != n_snps:
            raise ValidationError(
                "GenotypeMatrix",
                "variant_ids length != n_snps",
                f"ids={self.variant_ids.shape[0]} n_snps={n_snps}",
            )

        if self.sample_ids.shape[0] != n_samples:
            raise ValidationError(
                "GenotypeMatrix",
                "sample_ids length != n_samples",
                f"ids={self.sample_ids.shape[0]} n_samples={n_samples}",
            )

        if len(set(self.variant_ids.tolist())) != n_snps:
            raise ValidationError(
                "GenotypeMatrix", "variant_ids contain duplicates"
            )

        if len(set(self.sample_ids.tolist())) != n_samples:
            raise ValidationError(
                "GenotypeMatrix", "sample_ids contain duplicates"
            )

        if self.ploidy < 1:
            raise ValidationError(
                "GenotypeMatrix",
                "ploidy must be a positive integer",
                f"ploidy={self.ploidy}",
            )

        if self.allele_mode not in ("alt_dosage", "ref_dosage"):
            raise ValidationError(
                "GenotypeMatrix",
                "unsupported allele_mode",
                f"allele_mode={self.allele_mode}",
            )

    # ------------------------------------------------------------------ #
    # Reserved
    # ------------------------------------------------------------------ #

    def to_tensor(self, batch_size: int | None = None):
        """Reserved for ML/DL pipelines. Not implemented in v0.1.0."""
        raise NotImplementedError(
            "to_tensor() is reserved for ML/DL pipelines."
        )