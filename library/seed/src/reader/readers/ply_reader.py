"""PLY (Stanford polygon) reader: ASCII and both binary byte orders."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels

_FIELDS = ["x", "y", "z", "v0", "v1", "v2"]

_TYPES = {
    "char": "i1", "int8": "i1",
    "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2",
    "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4",
    "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4",
    "double": "f8", "float64": "f8",
}

_FORMATS = {
    "ascii": None,
    "binary_little_endian": "<",
    "binary_big_endian": ">",
}


def _split_parts(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_header(raw: bytes) -> tuple[str, list[dict], bytes]:
    marker = raw.find(b"end_header")
    if marker < 0:
        raise ReaderError("PLY reader: missing 'end_header'")
    newline = raw.find(b"\n", marker)
    header_end = len(raw) if newline < 0 else newline + 1
    header = raw[:marker].decode("utf-8", "replace")
    lines = _split_parts(header)
    if not lines or lines[0] != "ply":
        raise ReaderError("PLY reader: file does not start with 'ply'")
    fmt = None
    elements: list[dict] = []
    current = None
    for line in lines[1:]:
        parts = line.split()
        key = parts[0]
        if key == "format":
            if len(parts) < 3:
                raise ReaderError(f"PLY reader: malformed format line {line!r}")
            fmt = parts[1]
            if not parts[2].strip():
                raise ReaderError(f"PLY reader: malformed format line {line!r}")
            if fmt not in _FORMATS:
                raise ReaderError(f"PLY reader: unsupported format {fmt!r}")
        elif key == "element":
            if len(parts) != 3:
                raise ReaderError(f"PLY reader: malformed element line {line!r}")
            try:
                count = int(parts[2])
            except ValueError as exc:
                raise ReaderError(f"PLY reader: invalid element count in {line!r}") from exc
            if count < 0:
                raise ReaderError(f"PLY reader: negative element count in {line!r}")
            current = {"name": parts[1], "count": count, "props": []}
            elements.append(current)
        elif key == "property":
            if current is None:
                raise ReaderError("PLY reader: property declared before any element")
            if len(parts) >= 5 and parts[1] == "list":
                try:
                    count_type = _TYPES[parts[2]]
                    item_type = _TYPES[parts[3]]
                except KeyError as exc:
                    raise ReaderError(f"PLY reader: unknown property type in {line!r}") from exc
                current["props"].append((parts[4], item_type, count_type))
            elif len(parts) >= 3:
                try:
                    value_type = _TYPES[parts[1]]
                except KeyError as exc:
                    raise ReaderError(f"PLY reader: unknown property type in {line!r}") from exc
                current["props"].append((parts[2], value_type, None))
            else:
                raise ReaderError(f"PLY reader: malformed property line {line!r}")
        elif key in ("comment", "obj_info"):
            continue
    if fmt is None:
        raise ReaderError("PLY reader: missing format declaration")
    return fmt, elements, raw[header_end:]


def _pick_face_property(element: dict) -> int | None:
    for index, (name, _item, count_type) in enumerate(element["props"]):
        if count_type is not None and name in ("vertex_indices", "vertex_index"):
            return index
    for index, (name, _item, count_type) in enumerate(element["props"]):
        if count_type is not None:
            return index
    return None


def _parse_ascii(body: bytes, elements: list[dict], max_faces: int) -> tuple[np.ndarray, list[list[int]], int]:
    try:
        tokens = body.decode("utf-8", "replace").split()
    except UnicodeDecodeError as exc:  # pragma: no cover - replace handles all bytes
        raise ReaderError(f"PLY reader: cannot decode ASCII body: {exc}") from exc
    position = 0
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    polygons = 0
    for element in elements:
        name = element["name"]
        props = element["props"]
        if name == "vertex":
            index = {prop[0]: i for i, prop in enumerate(props)}
            for axis in ("x", "y", "z"):
                if axis not in index:
                    raise ReaderError(f"PLY reader: vertex element has no {axis!r} property")
            for _ in range(element["count"]):
                row: dict[str, float] = {}
                for prop_name, item_type, count_type in props:
                    if count_type is None:
                        if position >= len(tokens):
                            raise ReaderError("PLY reader: ASCII body ends inside a vertex")
                        row[prop_name] = _number(tokens[position], prop_name)
                        position += 1
                    else:
                        position = _skip_ascii_list(tokens, position, prop_name)
                if position > len(tokens):
                    raise ReaderError("PLY reader: ASCII body ends inside a vertex")
                vertices.append([row["x"], row["y"], row["z"]])
        elif name == "face":
            face_prop = _pick_face_property(element)
            if face_prop is None:
                raise ReaderError("PLY reader: face element has no list property")
            for _ in range(element["count"]):
                for prop_index, (prop_name, item_type, count_type) in enumerate(props):
                    if count_type is None:
                        if position >= len(tokens):
                            raise ReaderError("PLY reader: ASCII body ends inside a face")
                        position += 1
                    else:
                        if position >= len(tokens):
                            raise ReaderError("PLY reader: ASCII body ends inside a face")
                        try:
                            count = int(tokens[position])
                        except ValueError as exc:
                            raise ReaderError(
                                f"PLY reader: invalid list length in {prop_name!r}") from exc
                        position += 1
                        if count < 0 or position + count > len(tokens):
                            raise ReaderError("PLY reader: truncated ASCII face list")
                        items = [int(value) for value in tokens[position:position + count]]
                        position += count
                        if prop_index == face_prop:
                            if count < 3:
                                raise ReaderError("PLY reader: face has fewer than three vertices")
                            polygons += count > 3
                            faces.append(items)
                        if len(faces) > max_faces:
                            raise ReaderError(f"PLY reader: more than max_faces={max_faces} faces")
        else:
            position = _skip_ascii_element(tokens, position, props, element["count"])
    return np.asarray(vertices, dtype=np.float64).reshape(-1, 3), faces, polygons


def _number(token: str, prop: str) -> float:
    try:
        return float(token)
    except ValueError as exc:
        raise ReaderError(f"PLY reader: invalid number {token!r} for {prop!r}") from exc


def _skip_ascii_list(tokens: list[str], position: int, prop: str) -> int:
    if position >= len(tokens):
        raise ReaderError("PLY reader: ASCII body ends inside a property")
    try:
        count = int(tokens[position])
    except ValueError as exc:
        raise ReaderError(f"PLY reader: invalid list length in {prop!r}") from exc
    if count < 0:
        raise ReaderError(f"PLY reader: negative list length in {prop!r}")
    position += 1 + count
    if position > len(tokens):
        raise ReaderError("PLY reader: truncated ASCII property list")
    return position


def _skip_ascii_element(tokens: list[str], position: int, props: list, count: int) -> int:
    for _ in range(count):
        for prop_name, _item, count_type in props:
            if count_type is None:
                position += 1
            else:
                position = _skip_ascii_list(tokens, position, prop_name)
    return position


def _binary_size(value_type: str) -> int:
    return np.dtype(value_type).itemsize


_STRUCT_FORMAT = {
    "u1": "B", "i1": "b", "u2": "H", "i2": "h",
    "u4": "I", "i4": "i", "u8": "Q", "i8": "q",
    "f4": "f", "f8": "d",
}


def _struct_format(value_type: str) -> str:
    try:
        return _STRUCT_FORMAT[value_type]
    except KeyError as exc:
        raise ReaderError(f"PLY reader: unsupported binary type {value_type!r}") from exc


def _parse_binary(
    body: bytes, elements: list[dict], endian: str, max_faces: int
) -> tuple[np.ndarray, list[list[int]], int]:
    offset = 0
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    polygons = 0
    for element in elements:
        name = element["name"]
        props = element["props"]
        if name == "vertex":
            index = {prop[0]: i for i, prop in enumerate(props)}
            for axis in ("x", "y", "z"):
                if axis not in index:
                    raise ReaderError(f"PLY reader: vertex element has no {axis!r} property")
            for row in range(element["count"]):
                if offset >= len(body):
                    raise ReaderError("PLY reader: binary body ends inside a vertex")
                values: dict[str, float] = {}
                cursor = offset
                for prop_name, item_type, count_type in props:
                    if count_type is None:
                        size = _binary_size(item_type)
                        if cursor + size > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a vertex")
                        value = struct.unpack_from(endian + _struct_format(item_type), body, cursor)[0]
                        cursor += size
                        values[prop_name] = float(value)
                    else:
                        size = _binary_size(count_type)
                        if cursor + size > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a vertex")
                        count = struct.unpack_from(endian + _struct_format(count_type), body, cursor)[0]
                        if count < 0:
                            raise ReaderError("PLY reader: negative vertex list length")
                        cursor += size + int(count) * _binary_size(item_type)
                        if cursor > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a vertex")
                offset = cursor
                vertices.append([values["x"], values["y"], values["z"]])
        elif name == "face":
            face_prop = _pick_face_property(element)
            if face_prop is None:
                raise ReaderError("PLY reader: face element has no list property")
            for _ in range(element["count"]):
                row_values = []
                for prop_index, (prop_name, item_type, count_type) in enumerate(props):
                    if count_type is None:
                        size = _binary_size(item_type)
                        if offset + size > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a face")
                        row_values.append(None)
                        offset += size
                    else:
                        count_size = _binary_size(count_type)
                        if offset + count_size > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a face")
                        count = struct.unpack_from(endian + _struct_format(count_type), body, offset)[0]
                        offset += count_size
                        if count < 0:
                            raise ReaderError("PLY reader: negative face list length")
                        needed = count * _binary_size(item_type)
                        if offset + needed > len(body):
                            raise ReaderError("PLY reader: binary body ends inside a face")
                        items = list(struct.unpack_from(endian + str(count) + _struct_format(item_type), body, offset))
                        offset += needed
                        if prop_index == face_prop:
                            if count < 3:
                                raise ReaderError(
                                    "PLY reader: face has fewer than three vertices")
                            polygons += count > 3
                            faces.append([int(value) for value in items])
                        if len(faces) > max_faces:
                            raise ReaderError(f"PLY reader: more than max_faces={max_faces} faces")
        else:
            for _ in range(element["count"]):
                for _prop_name, item_type, count_type in props:
                    if count_type is None:
                        offset += _binary_size(item_type)
                    else:
                        if offset + _binary_size(count_type) > len(body):
                            raise ReaderError("PLY reader: binary body ends inside an element")
                        count = struct.unpack_from(endian + _struct_format(count_type), body, offset)[0]
                        offset += _binary_size(count_type) + count * _binary_size(item_type)
                    if offset > len(body):
                        raise ReaderError("PLY reader: binary body ends inside an element")
    return np.asarray(vertices, dtype=np.float64).reshape(-1, 3), faces, polygons


class PlyReader(Reader):
    provider = 'operon-readers'
    """Parse a PLY mesh (ASCII or binary, either byte order) into a table."""
    parameters_file = 'ply_reader.PlyReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'PlyReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Read a PLY polygon mesh',
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
     'description': ('Read an ASCII or binary PLY polygon mesh as one table: '
                     'vertex rows carry x/y/z and face rows carry three vertex indices.'),
     'extensions': ['.ply'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['element', 'field'],
                    'labels': {'element': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        path = Path(path)
        if len(dims) != 2:
            raise ReaderError(f"PLY reader requires exactly two dims, got {dims}")
        element_dim, field_dim = dims
        triangulate = bool(args.get("triangulate", True))
        max_faces = int(args.get("max_faces") or 1000000)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"PLY reader: cannot read {path}: {exc}") from exc
        if not raw:
            raise ReaderError("PLY reader: file is empty")
        fmt, elements, body = _parse_header(raw)
        vertex_element = next((e for e in elements if e["name"] == "vertex"), None)
        if vertex_element is None:
            raise ReaderError("PLY reader: no vertex element declared")
        if fmt == "ascii":
            vertices, faces, polygons = _parse_ascii(body, elements, max_faces)
        else:
            vertices, faces, polygons = _parse_binary(
                body, elements, _FORMATS[fmt], max_faces)
        if vertices.shape[0] == 0:
            raise ReaderError("PLY reader: file has no vertices")
        triangles: list[list[int]] = []
        for face in faces:
            if len(face) < 3:
                raise ReaderError("PLY reader: face has fewer than three vertices")
            if any(index < 0 or index >= vertices.shape[0] for index in face):
                raise ReaderError(
                    "PLY reader: face references a vertex outside the declared range")
            if len(face) == 3:
                triangles.append(face)
            elif not triangulate:
                raise ReaderError(
                    "PLY reader: polygon faces need triangulate=true")
            else:
                for position in range(1, len(face) - 1):
                    triangles.append([face[0], face[position], face[position + 1]])
            if len(triangles) > max_faces:
                raise ReaderError(f"PLY reader: more than max_faces={max_faces} faces")
        face_array = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
        n_vertices = vertices.shape[0]
        n_faces = face_array.shape[0]
        data = np.full((n_vertices + n_faces, 6), np.nan, dtype=np.float64)
        data[:n_vertices, :3] = vertices
        data[n_vertices:, 3:] = face_array
        names = [f"vertex{i}" for i in range(n_vertices)] + [
            f"face{j}" for j in range(n_faces)]
        face_element = next((e for e in elements if e["name"] == "face"), None)
        out = Form(
            data=compact_numeric(data),
            dims=[element_dim, field_dim],
            labels={element_dim: unique_labels(names, element_dim, "ply"),
                    field_dim: {name: i for i, name in enumerate(_FIELDS)}},
            info={
                "missing_code": np.nan,
                "format": fmt,
                "n_vertices": int(n_vertices),
                "n_faces": int(n_faces),
                "polygons": int(polygons),
                "triangulated": bool(triangulate),
                "elements": [element["name"] for element in elements],
                "face_property": None if face_element is None else
                face_element["props"][_pick_face_property(face_element) or 0][0],
            },
        )
        out.validate()
        return out
