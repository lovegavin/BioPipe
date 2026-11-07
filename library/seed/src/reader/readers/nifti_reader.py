"""NIfTI-1 volume reader."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader

_DTYPES = {
    2: ("u1", "uint8"),
    4: ("i2", "int16"),
    8: ("i4", "int32"),
    16: ("f4", "float32"),
    64: ("f8", "float64"),
    256: ("i1", "int8"),
    512: ("u2", "uint16"),
    768: ("u4", "uint32"),
    1024: ("i8", "int64"),
    1280: ("u8", "uint64"),
}


def _order(header: bytes) -> str:
    if len(header) < 348:
        raise ReaderError("NIfTI reader: file is smaller than the 348-byte header")
    for order in ("<", ">"):
        if struct.unpack(order + "i", header[:4])[0] == 348:
            return order
    raise ReaderError("NIfTI reader: sizeof_hdr is not 348; this is not a NIfTI-1 file")


def _quaternion_affine(header, order, pixdim, qform_code):
    b, c, d = struct.unpack(order + "3f", header[256:268])
    a_squared = 1.0 - (b * b + c * c + d * d)
    a = float(np.sqrt(a_squared)) if a_squared > 0.0 else 0.0
    rotation = np.array([
        [a * a + b * b - c * c - d * d, 2 * (b * c - a * d), 2 * (b * d + a * c)],
        [2 * (b * c + a * d), a * a + c * c - b * b - d * d, 2 * (c * d - a * b)],
        [2 * (b * d - a * c), 2 * (c * d + a * b), a * a + d * d - c * c - b * b],
    ], dtype=np.float64)
    if pixdim[0] < 0.0:
        rotation[:, 2] *= -1.0
    affine = np.eye(4, dtype=np.float64)
    affine[:3, :3] = rotation * np.asarray(pixdim[1:4], dtype=np.float64)
    affine[:3, 3] = struct.unpack(order + "3f", header[268:280])
    return affine


def _affine(header, order, pixdim, qform_code, sform_code):
    if sform_code > 0:
        affine = np.eye(4, dtype=np.float64)
        affine[0, :] = struct.unpack(order + "4f", header[280:296])
        affine[1, :] = struct.unpack(order + "4f", header[296:312])
        affine[2, :] = struct.unpack(order + "4f", header[312:328])
        return affine
    if qform_code > 0:
        return _quaternion_affine(header, order, pixdim, qform_code)
    affine = np.eye(4, dtype=np.float64)
    affine[0, 0], affine[1, 1], affine[2, 2] = pixdim[1], pixdim[2], pixdim[3]
    return affine


class NiftiReader(Reader):
    """Read single-file NIfTI-1 volumes as slices by flattened voxels."""
    provider = "operon-readers"
    parameters_file = "nifti_reader.NiftiReader.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "NiftiReader",
        "version": "1.0.0",
        "kind": "reader",
        "title": "Read a NIfTI-1 volume",
        "category": "Data",
        "contracts": {"version": 1, "inputs": [],
                      "output": {"version": 1, "numeric": True,
                                 "info": {"missing_code": {"type": ["number", "null"]}},
                                 "dims": [], "labels": [], "parallel": [],
                                 "ndim": 2, "axis_fields": [], "info_open": True}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "description": (
            "Read a single-file NIfTI-1 volume as a matrix of slices by "
            "flattened in-plane voxels, applying scl_slope/scl_inter and "
            "preserving the header geometry and affine."
        ),
        "extensions": [".nii"],
        "requires_siblings": [],
        "excludes_siblings": [],
        "handles_compression": False,
        "file_input": {"dims": ["slice", "voxel"],
                       "labels": {"slice": "auto", "voxel": "builtin"}},
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"NIfTI reader requires exactly two dims, got {dims}")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"NIfTI reader: cannot read {path}: {exc}") from exc
        header = raw[:348]
        order = _order(header)
        magic = header[344:348]
        if magic != b"n+1\x00":
            raise ReaderError(
                "NIfTI reader: only single-file NIfTI-1 images (magic n+1) are supported"
            )
        dim = struct.unpack(order + "8h", header[40:56])
        ndim = int(dim[0])
        if ndim < 2 or ndim > 3:
            raise ReaderError(
                f"NIfTI reader: only 2-D and 3-D images are supported, got {ndim}-D"
            )
        shape = [int(value) for value in dim[1:ndim + 1]]
        if ndim == 2:
            shape.append(1)
        nx, ny, nz = shape
        if nx < 1 or ny < 1 or nz < 1:
            raise ReaderError(f"NIfTI reader: invalid spatial dimensions {shape}")
        datatype = struct.unpack(order + "h", header[70:72])[0]
        if datatype not in _DTYPES:
            raise ReaderError(f"NIfTI reader: unsupported datatype code {datatype}")
        code, name = _DTYPES[datatype]
        pixdim = struct.unpack(order + "8f", header[76:108])
        qform_code = struct.unpack(order + "h", header[252:254])[0]
        sform_code = struct.unpack(order + "h", header[254:256])[0]
        slope = float(struct.unpack(order + "f", header[112:116])[0])
        intercept = float(struct.unpack(order + "f", header[116:120])[0])
        offset = int(struct.unpack(order + "f", header[108:112])[0] or 352)
        count = nx * ny * nz
        itemsize = np.dtype(code).itemsize
        expected = offset + count * itemsize
        if offset < 348:
            raise ReaderError(f"NIfTI reader: vox_offset {offset} points inside the header")
        if expected > len(raw):
            raise ReaderError(
                f"NIfTI reader: header describes {nx}x{ny}x{nz} ({expected} bytes) "
                f"but the file has {len(raw)} bytes"
            )
        start = int(args.get("slice_start") or 0)
        stop = args.get("slice_stop")
        stop = nz if stop is None or stop == "" else int(stop)
        if start < 0 or stop <= start or stop > nz:
            raise ReaderError(
                f"NIfTI reader: slice range {start}..{stop} is outside 0..{nz}"
            )
        max_cells = int(args.get("max_cells") or 4000000)
        cells = (stop - start) * ny * nx
        if cells > max_cells:
            raise ReaderError(
                f"NIfTI reader: {stop - start} slices x {nx} x {ny} is {cells} voxels, "
                f"above max_cells={max_cells}; narrow the slice range or raise max_cells"
            )
        values = np.frombuffer(
            raw[offset:offset + count * itemsize],
            dtype=np.dtype(order + code), count=count,
        ).reshape(nz, ny, nx).astype(np.float64)
        if slope != 0.0 and np.isfinite(slope):
            values = values * slope + intercept
        matrix = values[start:stop].reshape(stop - start, ny * nx)
        affine = _affine(header, order, pixdim, qform_code, sform_code)
        description = header[148:228].split(b"\\x00")[0].decode("utf-8", "replace").strip()
        intent = struct.unpack(order + "h", header[68:70])[0]
        cal_max = float(struct.unpack(order + "f", header[124:128])[0])
        cal_min = float(struct.unpack(order + "f", header[128:132])[0])
        slice_labels = {str(start + i): i for i in range(stop - start)}
        voxel_labels = {str(i): i for i in range(ny * nx)}
        out = Form(
            data=compact_numeric(matrix),
            dims=list(dims),
            labels={dims[0]: slice_labels, dims[1]: voxel_labels},
            info={"missing_code": np.nan, "format": "NIfTI-1",
                  "byte_order": "little" if order == "<" else "big",
                  "ndim": ndim, "nx": nx, "ny": ny, "nz": nz,
                  "datatype": datatype, "datatype_name": name,
                  "pixdim": [float(value) for value in pixdim],
                  "voxel_size": [float(value) for value in pixdim[1:4]],
                  "affine": affine.tolist(), "qform_code": int(qform_code),
                  "sform_code": int(sform_code), "vox_offset": offset,
                  "scl_slope": slope, "scl_inter": intercept,
                  "scaled": bool(slope != 0.0 and np.isfinite(slope)),
                  "intent_code": int(intent), "cal_min": cal_min,
                  "cal_max": cal_max, "description": description,
                  "slice_start": start, "slice_stop": stop},
        )
        out.validate()
        return out
