"""MRC/CCP4 electron microscopy volume reader."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader

_MODES = {0: ("i1", "int8"), 1: ("i2", "int16"), 2: ("f4", "float32"),
          6: ("u2", "uint16")}

_LAYOUTS = {
    "ccp4": {"origin": 196, "machst": 212, "rms": 216, "nlabl": 220,
             "label": 224, "exttyp": 104, "nversion": 108},
    "mrc2014": {"origin": 124, "machst": 140, "rms": 144, "nlabl": 148,
                "label": 152, "exttyp": 116, "nversion": 120},
}


def _layout(raw: bytes) -> str:
    if raw[208:212] == b"MAP ":
        return "ccp4"
    if raw[136:140] == b"MAP ":
        return "mrc2014"
    return "ccp4"


def _plausible(order: str, raw: bytes):
    try:
        nx, ny, nz, mode = struct.unpack(order + "4i", raw[:16])
    except struct.error:
        return None
    if not (1 <= nx <= 2 ** 20 and 1 <= ny <= 2 ** 20 and 1 <= nz <= 2 ** 20):
        return None
    if mode not in _MODES:
        return None
    nsymbt = struct.unpack(order + "i", raw[92:96])[0]
    if nsymbt < 0:
        return None
    return nx, ny, nz, mode


def _detect_order(raw: bytes, layout: str):
    stamp = raw[_LAYOUTS[layout]["machst"]:_LAYOUTS[layout]["machst"] + 4]
    if stamp[0] == 0x44:
        return "<"
    if stamp[0] == 0x11:
        return ">"
    for order in ("<", ">"):
        if _plausible(order, raw) is not None:
            return order
    raise ReaderError("MRC reader: cannot determine the byte order of the header")


class MrcReader(Reader):
    provider = 'operon-readers'
    """Read MRC/CCP4 volumes as a slice by flattened-voxel matrix."""
    parameters_file = 'mrc_reader.MrcReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'MrcReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Read an MRC/CCP4 volume',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': True}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': ('Read an MRC/CCP4 electron-microscopy volume as a matrix of '
                     'slices by flattened in-plane voxels, preserving the header '
                     'geometry and voxel size.'),
     'extensions': ['.mrc', '.mrcs'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['slice', 'voxel'],
                    'labels': {'slice': 'auto', 'voxel': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"MRC reader requires exactly two dims, got {dims}")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"MRC reader: cannot read {path}: {exc}") from exc
        if len(raw) < 1024:
            raise ReaderError(
                f"MRC reader: file is {len(raw)} bytes, smaller than the 1024-byte header"
            )
        header = raw[:1024]
        layout = _layout(header)
        offsets = _LAYOUTS[layout]
        order = _detect_order(header, layout)
        dims_hdr = _plausible(order, header)
        if dims_hdr is None:
            raise ReaderError("MRC reader: header dimensions or mode are not valid")
        nx, ny, nz, mode = dims_hdr
        nsymbt = struct.unpack(order + "i", header[92:96])[0]
        dtype_code, mode_name = _MODES[mode]
        itemsize = np.dtype(dtype_code).itemsize
        data_offset = 1024 + nsymbt
        slice_bytes = nx * ny * itemsize
        expected = data_offset + slice_bytes * nz
        if expected > len(raw):
            raise ReaderError(
                f"MRC reader: header describes {nx}x{ny}x{nz} with mode {mode} "
                f"({expected} bytes) but the file has {len(raw)} bytes"
            )
        start = int(args.get("slice_start") or 0)
        stop = args.get("slice_stop")
        stop = nz if stop is None or stop == "" else int(stop)
        if start < 0 or stop <= start or stop > nz:
            raise ReaderError(
                f"MRC reader: slice range {start}..{stop} is outside 0..{nz}"
            )
        count = stop - start
        max_cells = int(args.get("max_cells") or 4000000)
        cells = count * ny * nx
        if cells > max_cells:
            raise ReaderError(
                f"MRC reader: {count} slices x {nx} x {ny} is {cells} voxels, above "
                f"max_cells={max_cells}; narrow the slice range or raise max_cells"
            )
        buffer = raw[data_offset + start * slice_bytes:data_offset + stop * slice_bytes]
        try:
            data = np.frombuffer(buffer, dtype=np.dtype(order + dtype_code))
        except ValueError as exc:
            raise ReaderError(f"MRC reader: cannot decode voxel data: {exc}") from exc
        data = data.reshape(count, ny, nx).astype(np.float64)
        matrix = data.reshape(count, ny * nx)
        maxima = struct.unpack(order + "3i", header[28:40])
        cella = struct.unpack(order + "3f", header[40:52])
        cellb = struct.unpack(order + "3f", header[52:64])
        origin = struct.unpack(order + "3f", header[offsets["origin"]:offsets["origin"] + 12])
        machst = header[offsets["machst"]:offsets["machst"] + 4]
        rms = struct.unpack(order + "f", header[offsets["rms"]:offsets["rms"] + 4])[0]
        nlabl = struct.unpack(order + "i", header[offsets["nlabl"]:offsets["nlabl"] + 4])[0]
        label_bytes = header[offsets["label"]:1024]
        text = label_bytes.split(b"\x00")[0].decode("utf-8", "replace")
        first_label = ""
        if nlabl > 0 and label_bytes:
            first_label = label_bytes[:80].split(b"\x00")[0].decode("utf-8", "replace").strip()
        voxel_size = [float(cella[i] / maxima[i]) if maxima[i] > 0 else float("nan")
                      for i in range(3)]
        slice_labels = {str(start + i): i for i in range(count)}
        voxel_labels = {str(i): i for i in range(ny * nx)}
        out = Form(
            data=compact_numeric(matrix),
            dims=list(dims),
            labels={dims[0]: slice_labels, dims[1]: voxel_labels},
            info={"missing_code": np.nan, "format": "MRC", "layout": layout,
                  "byte_order": "little" if order == "<" else "big",
                  "nx": nx, "ny": ny, "nz": nz, "mode": mode, "mode_name": mode_name,
                  "voxel_size": voxel_size, "cella": list(cella), "cellb": list(cellb),
                  "origin": list(origin),
                  "machine_stamp": machst.hex(),
                  "nsymbt": nsymbt, "rms": float(rms), "nlabl": nlabl,
                  "label": first_label or text, "slice_start": start,
                  "slice_stop": stop},
        )
        out.validate()
        return out
