# src/core/forms/form.py
"""Form — the only in-memory data structure."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.core.errors import ValidationError


@dataclass
class Form:
    """An n-dimensional tensor with ordered axis names and label maps.

    Parameters
    ----------
    data : np.ndarray
        The tensor. No headers.
    dims : list[str]
        Axis names, in axis order. ``len(dims) == data.ndim``.
    labels : dict[str, dict[str, int]]
        ``{dim_name: {label: position}}``. Positions are 0-based
        indices within ``data`` along that axis. Optional.
    info : dict
        Form-level attributes.
    """

    data: np.ndarray
    dims: list[str]
    labels: dict[str, dict[str, int]] = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Axis lookup
    # ------------------------------------------------------------------ #

    def axis(self, name: str) -> int:
        """Return the axis index of the named dimension."""
        try:
            return self.dims.index(name)
        except ValueError:
            raise ValidationError(
                "Form",
                f"unknown dim '{name}'",
                f"available: {self.dims}",
            )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if not isinstance(self.data, np.ndarray):
            raise ValidationError("Form", "data must be a numpy array")

        if len(self.dims) != self.data.ndim:
            raise ValidationError(
                "Form",
                f"len(dims)={len(self.dims)} != data.ndim={self.data.ndim}",
            )

        if len(set(self.dims)) != len(self.dims):
            raise ValidationError("Form", "dims contain duplicates")

        for dim_name, mapping in self.labels.items():
            if dim_name not in self.dims:
                raise ValidationError(
                    "Form", f"labels reference unknown dim '{dim_name}'"
                )
            size = self.data.shape[self.axis(dim_name)]
            for lab, pos in mapping.items():
                if not isinstance(pos, int):
                    raise ValidationError(
                        "Form",
                        f"labels.{dim_name}.{lab} must be an int",
                    )
                if not 0 <= pos < size:
                    raise ValidationError(
                        "Form",
                        f"labels.{dim_name}.{lab}={pos} out of range "
                        f"(axis size {size})",
                    )