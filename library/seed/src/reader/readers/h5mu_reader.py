"""MuData (``.h5mu``) reader.

MuData stores one or more modalities under ``/mod/<name>``. Each modality
carries its own ``X`` matrix plus ``obs``/``var`` groups whose ``_index``
datasets hold the sample and feature names. ``X`` may be a dense HDF5
dataset or a sparse CSR group (``data``/``indices``/``indptr``/``shape``).

The reader returns a dense ``Form`` for one modality. When the file holds
several modalities, ``modality`` selects one; a single-modality file is
read without it.
"""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


def _decode(values) -> list[str]:
    names: list[str] = []
    for value in values:
        if isinstance(value, bytes):
            names.append(value.decode("utf-8"))
        else:
            names.append(str(value))
    return names


def _index_names(group: h5py.Group, dim: str, size: int) -> list[str]:
    axis = group.get(dim)
    if not isinstance(axis, h5py.Group) or "_index" not in axis:
        return [f"{dim}_{index}" for index in range(size)]
    names = _decode(axis["_index"][:])
    if len(names) != size:
        raise ReaderError(
            f"H5mu reader: {dim} index has {len(names)} names for {size} positions"
        )
    return names


def _read_matrix(node, label: str) -> tuple[np.ndarray, str]:
    if isinstance(node, h5py.Group):
        for key in ("data", "indices", "indptr"):
            if key not in node:
                raise ReaderError(f"H5mu reader: sparse {label} group is missing {key!r}")
        from scipy.sparse import csr_matrix

        shape = node.attrs.get("shape")
        if shape is None and "shape" in node:
            shape = node["shape"][:]
        if shape is None:
            raise ReaderError(f"H5mu reader: sparse {label} group has no shape")
        matrix = csr_matrix(
            (np.asarray(node["data"][:], dtype=np.float64),
             np.asarray(node["indices"][:], dtype=np.int64),
             np.asarray(node["indptr"][:], dtype=np.int64)),
            shape=tuple(int(value) for value in shape),
        )
        return np.asarray(matrix.toarray(), dtype=np.float64), "sparse"
    data = np.asarray(node[:], dtype=np.float64)
    if data.ndim != 2:
        raise ReaderError(f"H5mu reader: {label} must be two-dimensional, got ndim={data.ndim}")
    return data, "dense"


class H5muReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'h5mu_reader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'H5muReader',
        'version': '1.0.0',
        'kind': 'reader',
        'title': 'MuData multimodal HDF5 reader',
        'category': 'Data',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'version': 1,
                'numeric': True,
                'info': {'missing_code': {'type': ['number', 'null']}},
                'dims': [],
                'labels': [],
                'parallel': [],
                'ndim': 2,
                'axis_fields': [],
                'info_open': True,
            },
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'dependencies': ['h5py>=3.10', 'scipy>=1.11'],
        'dependency_imports': ['h5py', 'scipy'],
        'description': 'Reads one modality from a MuData .h5mu container into a sample-by-feature matrix.',
        'extensions': ['.h5mu'],
        'requires_siblings': [],
        'excludes_siblings': [],
        'handles_compression': False,
        'file_input': {'dims': ['sample', 'feature'],
                       'labels': {'sample': 'builtin', 'feature': 'builtin'}},
    }

    def read(self, path: Path, dims: list[str], labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"H5mu reader requires exactly two dims, got {dims}")
        sample_dim, feature_dim = dims
        for dim in (sample_dim, feature_dim):
            rule = (labels or {}).get(dim)
            if rule not in (None, "builtin", "auto"):
                raise ReaderError(
                    f"H5mu reader: custom label rules are not supported for {dim!r}; "
                    "use the obs/var index stored in the file"
                )
        modality = args.get("modality")
        layer = args.get("layer")
        with h5py.File(path, "r") as handle:
            if "mod" not in handle or not isinstance(handle["mod"], h5py.Group):
                raise ReaderError("H5mu reader: file has no /mod group")
            mods = sorted(handle["mod"].keys())
            if not mods:
                raise ReaderError("H5mu reader: file has no modalities")
            if modality:
                if modality not in mods:
                    raise ReaderError(
                        f"H5mu reader: modality {modality!r} not found; available: {mods}"
                    )
                selected = modality
            elif len(mods) == 1:
                selected = mods[0]
            else:
                raise ReaderError(
                    f"H5mu reader: file contains {len(mods)} modalities {mods}; pass modality"
                )
            group = handle["mod"][selected]
            if layer:
                layers = group.get("layers")
                if not isinstance(layers, h5py.Group) or layer not in layers:
                    raise ReaderError(
                        f"H5mu reader: modality {selected!r} has no layer {layer!r}"
                    )
                node = layers[layer]
            else:
                if "X" not in group:
                    raise ReaderError(f"H5mu reader: modality {selected!r} has no X matrix")
                node = group["X"]
            data, storage = _read_matrix(node, "X" if layer is None else f"layers/{layer}")
            sample_names = _index_names(group, "obs", data.shape[0])
            feature_names = _index_names(group, "var", data.shape[1])

        rule = (labels or {}).get(sample_dim)
        if rule == "auto":
            sample_names = [str(index) for index in range(len(sample_names))]
        rule = (labels or {}).get(feature_dim)
        if rule == "auto":
            feature_names = [str(index) for index in range(len(feature_names))]

        info = {
            "missing_code": np.nan,
            "representation": "h5mu",
            "format": storage,
            "modality": selected,
            "layer": layer,
            "n_modalities": len(mods),
            "n_obs": int(data.shape[0]),
            "n_vars": int(data.shape[1]),
        }
        form = Form(
            data=compact_numeric(data),
            dims=list(dims),
            labels={
                sample_dim: unique_labels(sample_names, sample_dim, "H5mu reader"),
                feature_dim: unique_labels(feature_names, feature_dim, "H5mu reader"),
            },
            info=info,
        )
        form.validate()
        return form
