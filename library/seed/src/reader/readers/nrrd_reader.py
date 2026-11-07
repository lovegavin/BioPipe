"""NRRD volume reader."""
from __future__ import annotations

import gzip
import re
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader

_TYPES = {
    "signed char": ("i1", "int8"),
    "int8": ("i1", "int8"),
    "uchar": ("u1", "uint8"),
    "unsigned char": ("u1", "uint8"),
    "uint8": ("u1", "uint8"),
    "short": ("i2", "int16"),
    "short int": ("i2", "int16"),
    "int16": ("i2", "int16"),
    "ushort": ("u2", "uint16"),
    "unsigned short": ("u2", "uint16"),
    "uint16": ("u2", "uint16"),
    "int": ("i4", "int32"),
    "int32": ("i4", "int32"),
    "uint": ("u4", "uint32"),
    "uint32": ("u4", "uint32"),
    "longlong": ("i8", "int64"),
    "long long": ("i8", "int64"),
    "int64": ("i8", "int64"),
    "ulonglong": ("u8", "uint64"),
    "unsigned long long": ("u8", "uint64"),
    "uint64": ("u8", "uint64"),
    "float": ("f4", "float32"),
    "double": ("f8", "float64"),
}

_VECTOR = re.compile(r"\(([^)]*)\)")


def _numbers(text):
    values = text.replace(",", " ").split()
    return [float(value) for value in values]


def _vector_list(value):
    vectors = []
    for body in _VECTOR.findall(value):
        numbers = _numbers(body)
        if numbers:
            vectors.append(numbers)
    return vectors


def _header(raw: bytes):
    if len(raw) < 8 or not raw.startswith(b"NRRD"):
        raise ReaderError("NRRD reader: file does not start with the NRRD magic")
    end = raw.find(b"\n\n")
    if end == -1:
        raise ReaderError("NRRD reader: header terminator (blank line) is missing")
    block = raw[:end].decode("latin-1")
    lines = block.splitlines()
    if not re.fullmatch(r"NRRD\d{4}", lines[0].strip()):
        raise ReaderError(f"NRRD reader: unsupported magic {lines[0]!r}")
    fields = {}
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ReaderError(f"NRRD reader: malformed header line {line!r}")
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields, end + 2


class NrrdReader(Reader):
    """Read NRRD volumes as slices by flattened voxels."""
    provider = "operon-readers"
    parameters_file = "nrrd_reader.NrrdReader.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "NrrdReader",
        "version": "1.0.0",
        "kind": "reader",
        "title": "Read a NRRD volume",
        "category": "Data",
        "contracts": {"version": 1, "inputs": [],
                      "output": {"version": 1, "numeric": True,
                                 "info": {"missing_code": {"type": ["number", "null"]}},
                                 "dims": [], "labels": [], "parallel": [],
                                 "ndim": 2, "axis_fields": [], "info_open": True}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "description": (
            "Read a NRRD volume (raw or gzip encoded, 2-D or 3-D) as a matrix "
            "of slices by flattened in-plane voxels, preserving the NRRD "
            "spacing, space origin and axis kinds."
        ),
        "extensions": [".nrrd"],
        "requires_siblings": [],
        "excludes_siblings": [],
        "handles_compression": False,
        "file_input": {"dims": ["slice", "voxel"],
                       "labels": {"slice": "auto", "voxel": "builtin"}},
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"NRRD reader requires exactly two dims, got {dims}")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"NRRD reader: cannot read {path}: {exc}") from exc
        fields, offset = _header(raw)
        if "data file" in fields:
            raise ReaderError(
                "NRRD reader: detached headers (data file) are not supported"
            )
        dimension = int(fields.get("dimension", "0"))
        if dimension < 2 or dimension > 3:
            raise ReaderError(
                f"NRRD reader: only 2-D and 3-D volumes are supported, got {dimension}-D"
            )
        sizes = [int(value) for value in fields.get("sizes", "").split()]
        if len(sizes) != dimension or any(value < 1 for value in sizes):
            raise ReaderError(f"NRRD reader: invalid sizes field {fields.get('sizes')!r}")
        type_name = fields.get("type", "").strip().lower()
        if type_name not in _TYPES:
            raise ReaderError(f"NRRD reader: unsupported type {type_name!r}")
        code, name = _TYPES[type_name]
        endian = fields.get("endian", "little").strip().lower()
        if endian not in ("little", "big"):
            raise ReaderError(f"NRRD reader: unsupported endian {endian!r}")
        order = "<" if endian == "little" else ">"
        encoding = fields.get("encoding", "raw").strip().lower()
        if encoding not in ("raw", "gzip", "gz"):
            raise ReaderError(f"NRRD reader: unsupported encoding {encoding!r}")
        line_skip = int(fields.get("line skip", "0") or 0)
        byte_skip = int(fields.get("byte skip", "0") or 0)
        for _ in range(max(line_skip, 0)):
            newline = raw.find(b"\n", offset)
            if newline == -1:
                raise ReaderError("NRRD reader: line skip runs past the end of the file")
            offset = newline + 1
        offset += max(byte_skip, 0)
        payload = raw[offset:]
        if encoding in ("gzip", "gz"):
            try:
                payload = gzip.decompress(payload)
            except OSError as exc:
                raise ReaderError(f"NRRD reader: cannot decompress gzip data: {exc}") from exc
        count = int(np.prod(sizes))
        itemsize = np.dtype(code).itemsize
        if len(payload) < count * itemsize:
            raise ReaderError(
                f"NRRD reader: header describes {count} values ({count * itemsize} bytes) "
                f"but the data section has {len(payload)} bytes"
            )
        array = np.frombuffer(payload[:count * itemsize],
                              dtype=np.dtype(order + code), count=count)
        if dimension == 2:
            values = array.reshape(sizes[1], sizes[0])
            nz = 1
            ny, nx = sizes[1], sizes[0]
        else:
            values = array.reshape(sizes[2], sizes[1], sizes[0])
            nz, ny, nx = sizes[2], sizes[1], sizes[0]
        start = int(args.get("slice_start") or 0)
        stop = args.get("slice_stop")
        stop = nz if stop is None or stop == "" else int(stop)
        if start < 0 or stop <= start or stop > nz:
            raise ReaderError(
                f"NRRD reader: slice range {start}..{stop} is outside 0..{nz}"
            )
        max_cells = int(args.get("max_cells") or 4000000)
        cells = (stop - start) * ny * nx
        if cells > max_cells:
            raise ReaderError(
                f"NRRD reader: {stop - start} slices x {nx} x {ny} is {cells} voxels, "
                f"above max_cells={max_cells}; narrow the slice range or raise max_cells"
            )
        matrix = values.reshape(nz, ny * nx)[start:stop].astype(np.float64)
        directions = _vector_list(fields.get("space directions", ""))
        origin = _vector_list(fields.get("space origin", ""))
        affine = np.eye(4, dtype=np.float64)
        if len(directions) >= dimension:
            affine[:3, :3] = np.column_stack([np.asarray(vector, dtype=np.float64)
                                              for vector in directions[:dimension]])
        if origin:
            affine[:3, 3] = np.asarray(origin[0], dtype=np.float64)
        slice_labels = {str(start + i): i for i in range(stop - start)}
        voxel_labels = {str(i): i for i in range(ny * nx)}
        out = Form(
            data=compact_numeric(matrix),
            dims=list(dims),
            labels={dims[0]: slice_labels, dims[1]: voxel_labels},
            info={"missing_code": np.nan, "format": "NRRD",
                  "byte_order": endian, "type": type_name,
                  "datatype": name, "dimension": dimension,
                  "sizes": sizes, "encoding": encoding,
                  "space": fields.get("space", ""),
                  "space_directions": directions, "space_origin": origin,
                  "kinds": fields.get("kinds", "").split(),
                  "affine": affine.tolist(),
                  "line_skip": line_skip, "byte_skip": byte_skip,
                  "slice_start": start, "slice_stop": stop},
        )
        out.validate()
        return out
