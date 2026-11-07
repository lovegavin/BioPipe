"""STL triangular mesh reader (binary and ASCII)."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels

_FIELDS = ["x", "y", "z", "v0", "v1", "v2"]


def _binary_count(raw: bytes) -> int | None:
    if len(raw) < 84:
        return None
    count = struct.unpack("<I", raw[80:84])[0]
    if count == 0:
        return None
    expected = 84 + 50 * count
    if len(raw) < expected:
        return None
    if raw[:5].lower() == b"solid" and len(raw) != expected:
        return None
    return count


def _parse_binary(raw: bytes, count: int) -> tuple[np.ndarray, np.ndarray]:
    dtype = np.dtype([("normal", "<f4", 3), ("vertices", "<f4", (3, 3)),
                      ("attr", "<u2")])
    try:
        records = np.frombuffer(raw[84:84 + 50 * count], dtype=dtype, count=count)
    except ValueError as exc:
        raise ReaderError(f"STL reader: cannot decode binary facets: {exc}") from exc
    vertices = records["vertices"].astype(np.float64).reshape(-1, 3)
    faces = np.arange(count * 3, dtype=np.int64).reshape(-1, 3)
    return vertices, faces


def _parse_ascii(text: str) -> tuple[np.ndarray, np.ndarray, str]:
    vertices = []
    triangles = 0
    name = ""
    seen_solid = False
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        keyword = parts[0].lower()
        if keyword == "solid":
            seen_solid = True
            if not name and len(parts) > 1:
                name = " ".join(parts[1:])
            continue
        if keyword == "vertex":
            if len(parts) != 4:
                raise ReaderError(f"STL reader: malformed vertex line {line.strip()!r}")
            try:
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            except ValueError as exc:
                raise ReaderError(f"STL reader: invalid vertex value in {line.strip()!r}") from exc
            continue
        if keyword == "facet":
            triangles += 1
    if not seen_solid:
        raise ReaderError("STL reader: missing 'solid' header in ASCII STL")
    if not vertices:
        raise ReaderError("STL reader: ASCII STL contains no vertices")
    array = np.asarray(vertices, dtype=np.float64).reshape(-1, 3)
    if array.shape[0] != 3 * triangles:
        raise ReaderError(
            f"STL reader: {triangles} facets but {array.shape[0]} vertices; "
            "each facet needs three vertices"
        )
    faces = np.arange(array.shape[0], dtype=np.int64).reshape(-1, 3)
    return array, faces, name


def _merge(vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    keys = np.round(vertices, 9)
    lookup: dict[tuple, int] = {}
    unique_rows = []
    indices = []
    for row in keys:
        key = (float(row[0]), float(row[1]), float(row[2]))
        position = lookup.get(key)
        if position is None:
            position = len(unique_rows)
            lookup[key] = position
            unique_rows.append((float(row[0]), float(row[1]), float(row[2])))
        indices.append(position)
    return np.asarray(unique_rows, dtype=np.float64), np.asarray(indices, dtype=np.int64)


class StlReader(Reader):
    provider = 'operon-readers'
    """Parse a binary or ASCII STL mesh into an element x field table."""
    parameters_file = 'stl_reader.StlReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'StlReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Read an STL triangular mesh',
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
     'description': ('Read a binary or ASCII STL triangular mesh as one table: '
                     'vertex rows carry x/y/z and facet rows carry three vertex indices.'),
     'extensions': ['.stl'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['element', 'field'],
                    'labels': {'element': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"STL reader requires exactly two dims, got {dims}")
        element_dim, field_dim = dims
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"STL reader: cannot read {path}: {exc}") from exc
        if not raw:
            raise ReaderError("STL reader: file is empty")
        merge_vertices = bool(args.get("merge_vertices", True))
        max_faces = int(args.get("max_faces") or 1000000)
        count = _binary_count(raw)
        if count is not None:
            if count > max_faces:
                raise ReaderError(f"STL reader: {count} facets exceed max_faces={max_faces}")
            header = raw[:80].split(b"\x00")[0].decode("utf-8", "replace").strip()
            vertices, faces = _parse_binary(raw, count)
            name = header
            fmt = "binary"
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
            if not text.lstrip().lower().startswith("solid"):
                raise ReaderError("STL reader: neither a valid binary nor ASCII STL file")
            vertices, faces, name = _parse_ascii(text)
            if faces.shape[0] > max_faces:
                raise ReaderError(
                    f"STL reader: {faces.shape[0]} facets exceed max_faces={max_faces}"
                )
            fmt = "ascii"
        if faces.shape[0] == 0:
            raise ReaderError("STL reader: no facets found")
        if merge_vertices:
            unique, indices = _merge(vertices)
        else:
            unique = np.round(vertices, 9)
            indices = np.arange(vertices.shape[0], dtype=np.int64)
        faces = indices[faces.reshape(-1)].reshape(-1, 3)
        n_vertices = unique.shape[0]
        n_faces = faces.shape[0]
        data = np.full((n_vertices + n_faces, 6), np.nan, dtype=np.float64)
        data[:n_vertices, :3] = unique
        data[n_vertices:, 3:] = faces
        names = [f"vertex{i}" for i in range(n_vertices)] + [
            f"face{j}" for j in range(n_faces)]
        out = Form(
            data=compact_numeric(data),
            dims=[element_dim, field_dim],
            labels={element_dim: unique_labels(names, element_dim, "stl"),
                    field_dim: {name: i for i, name in enumerate(_FIELDS)}},
            info={"missing_code": np.nan, "format": fmt, "n_vertices": int(n_vertices),
                  "n_faces": int(n_faces), "merge_vertices": bool(merge_vertices),
                  "name": name[:80]},
        )
        out.validate()
        return out
