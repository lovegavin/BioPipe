# src/core/forms/form.py
"""Form — the only in-memory data structure.

An n-dimensional tensor with named axes, per-axis label maps, and
an info dictionary.

Axis-parallel info
------------------
Some info entries are arrays whose length equals the size of a named
axis (for example ``chrom`` and ``pos`` for the ``variant`` axis of
a VCF). Such entries must be declared in ``axis_info[dim]`` so that
``subset_axis`` can keep them in sync when the axis is trimmed. No
inference by length is performed.

Label coverage
--------------
Every position along every axis must have a label. ``validate()``
refuses a form whose labels do not cover positions 0..size-1.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.core.errors import ValidationError


@dataclass
class Form:
    """An n-dimensional tensor with named axes and label maps.

    Parameters
    ----------
    data : np.ndarray
        The tensor. No headers.
    dims : list[str]
        Axis names, in axis order. ``len(dims) == data.ndim``.
    labels : dict[str, dict[str, int]]
        One entry per dim. Maps ``{dim_name: {label: position}}``.
        Every axis position must appear as a value in the mapping.
    info : dict
        Form-level attributes. Non-array values are passed through
        unchanged.
    axis_info : dict[str, list[str]]
        ``{dim_name: [info_key, ...]}``. Each listed info key must be
        a list or 1-D array whose length equals the size of that
        axis. ``subset_axis`` trims those entries along with data.
    """

    data: np.ndarray
    dims: list[str]
    labels: dict[str, dict[str, int]] = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    axis_info: dict[str, list[str]] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #

    def axis(self, name: str) -> int:
        try:
            return self.dims.index(name)
        except ValueError:
            raise ValidationError(
                "Form",
                f"unknown dim '{name}'",
                f"available: {self.dims}",
            )

    def get_parallel(self, field: str, dim: str) -> np.ndarray | None:
        """Return an array parallel to ``dim`` identified by ``field``.

        Looks first for a data column with that name in ``labels[dim]``.
        Then looks in ``info`` if ``field`` is declared in
        ``axis_info[dim]``. Returns None if neither applies.
        """
        if dim in self.labels and field in self.labels[dim]:
            pos = self.labels[dim][field]
            axis = self.dims.index(dim)
            return np.take(self.data, pos, axis=axis)
        if dim in self.axis_info and field in self.axis_info[dim]:
            if field in self.info:
                return np.asarray(self.info[field])
        return None

    # ------------------------------------------------------------------ #
    # Subsetting
    # ------------------------------------------------------------------ #

    def subset_axis(self, dim: str, indices) -> "Form":
        """Return a new form restricted to ``indices`` along ``dim``.

        Trims data, labels, and only those info entries declared in
        ``axis_info[dim]``. Nothing else is touched.
        """
        if dim not in self.dims:
            raise ValidationError("Form", f"unknown dim '{dim}'")
        axis = self.dims.index(dim)
        indices = np.asarray(indices, dtype=np.intp) if len(indices) == 0 else np.asarray(indices)
        axis_size = self.data.shape[axis]
        if indices.ndim != 1 or indices.dtype.kind not in "iu" or len(set(indices.tolist())) != len(indices):
            raise ValidationError("Form", "subset indices must be unique integers")
        if np.any(indices < 0) or np.any(indices >= axis_size):
            raise ValidationError("Form", "subset index out of range")

        # Labels must cover every position before subsetting.
        pos_to_label = {v: k for k, v in self.labels[dim].items()}
        missing = [i for i in range(axis_size) if i not in pos_to_label]
        if missing:
            raise ValidationError(
                "Form",
                f"dim '{dim}' has unlabeled positions",
                f"first missing: {missing[:5]}",
            )

        new_data = np.take(self.data, indices, axis=axis).copy()

        new_dim_labels = {
            pos_to_label[int(old)]: new_pos
            for new_pos, old in enumerate(indices)
        }
        new_labels = {k: dict(v) for k, v in self.labels.items()}
        new_labels[dim] = new_dim_labels

        from .metadata import project_metadata
        new_info, new_axis_info = project_metadata(self, {dim: indices})
        return Form(
            data=new_data,
            dims=list(self.dims),
            labels=new_labels,
            info=new_info,
            axis_info=new_axis_info,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if not isinstance(self.data, np.ndarray):
            raise ValidationError("Form", "data must be a numpy array")
        if not isinstance(self.info, dict) or not isinstance(self.axis_info, dict):
            raise ValidationError("Form", "info and axis_info must be dictionaries")
        if any(not isinstance(dim, str) or not dim for dim in self.dims):
            raise ValidationError("Form", "dimensions must be nonempty strings")

        if len(self.dims) != self.data.ndim:
            raise ValidationError(
                "Form",
                f"len(dims)={len(self.dims)} != data.ndim={self.data.ndim}",
            )

        if len(set(self.dims)) != len(self.dims):
            raise ValidationError("Form", "dims contain duplicates")

        for dim_name in self.dims:
            if dim_name not in self.labels:
                raise ValidationError(
                    "Form",
                    f"dim '{dim_name}' has no labels entry",
                    f"labels cover: {sorted(self.labels)}",
                )

        for dim_name, mapping in self.labels.items():
            if dim_name not in self.dims:
                raise ValidationError(
                    "Form", f"labels reference unknown dim '{dim_name}'"
                )
            size = self.data.shape[self.axis(dim_name)]

            # Every position must be labeled.
            seen = set()
            for lab, pos in mapping.items():
                if not isinstance(pos, int) or isinstance(pos, bool):
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
                if pos in seen:
                    raise ValidationError("Form", f"dim '{dim_name}' has multiple labels for position {pos}")
                seen.add(pos)
            unlabeled = set(range(size)) - seen
            if unlabeled:
                raise ValidationError(
                    "Form",
                    f"dim '{dim_name}' has unlabeled positions",
                    f"first missing: {sorted(unlabeled)[:5]}",
                )

        bound_fields = set()
        for dim_name, keys in self.axis_info.items():
            if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
                raise ValidationError("Form", "axis_info entries must be lists of field names")
            if dim_name not in self.dims:
                raise ValidationError(
                    "Form",
                    f"axis_info references unknown dim '{dim_name}'",
                )
            size = self.data.shape[self.axis(dim_name)]
            for k in keys:
                if k in bound_fields:
                    raise ValidationError("Form", f"info.{k} must bind to exactly one axis")
                bound_fields.add(k)
                if k not in self.info:
                    raise ValidationError(
                        "Form",
                        f"axis_info['{dim_name}'] lists '{k}' but it is "
                        f"not in info",
                    )
                v = self.info[k]
                if isinstance(v, np.ndarray) and v.ndim != 1:
                    raise ValidationError("Form", f"info.{k} must be a one-dimensional array")
                if isinstance(v, list) and any(isinstance(item, (list, tuple, np.ndarray)) for item in v):
                    raise ValidationError("Form", f"info.{k} must be a one-dimensional list")
                if not isinstance(v, (list, np.ndarray)):
                    raise ValidationError(
                        "Form",
                        f"info['{k}'] declared parallel to '{dim_name}' "
                        f"but is not a list or array",
                    )
                if len(v) != size:
                    raise ValidationError(
                        "Form",
                        f"info['{k}'] declared parallel to '{dim_name}' "
                        f"but has length {len(v)} != {size}",
                    )
        encoders = self.info.get("encoders", {})
        if not isinstance(encoders, dict):
            raise ValidationError("Form", "info.encoders must be a dimension mapping")
        for dim, fields in encoders.items():
            if dim not in self.dims or not isinstance(fields, dict):
                raise ValidationError("Form", f"invalid encoder dimension {dim}")
            for key in fields:
                if key not in self.labels[dim] and key not in self.axis_info.get(dim, []):
                    raise ValidationError("Form", f"orphan encoder {dim}.{key}")
