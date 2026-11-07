"""Wavefront OBJ mesh reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels

_FIELDS = ["x", "y", "z", "v0", "v1", "v2"]


class ObjReader(Reader):
    provider = 'operon-readers'
    """Parse a Wavefront OBJ mesh into an element x field table."""
    parameters_file = 'obj_reader.ObjReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ObjReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Read a Wavefront OBJ mesh',
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
     'description': ('Read a Wavefront OBJ triangular mesh as one table: vertex rows '
                     'carry x/y/z and face rows carry three vertex indices. Polygon '
                     'faces are fan-triangulated.'),
     'extensions': ['.obj'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['element', 'field'],
                    'labels': {'element': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"OBJ reader requires exactly two dims, got {dims}")
        element_dim, field_dim = dims
        triangulate = bool(args.get("triangulate", True))
        max_faces = int(args.get("max_faces") or 1000000)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReaderError(f"OBJ reader: cannot read {path}: {exc}") from exc
        except UnicodeDecodeError as exc:
            raise ReaderError(f"OBJ reader: file is not valid UTF-8: {exc}") from exc
        vertices: list[list[float]] = []
        faces: list[list[int]] = []
        objects: list[str] = []
        polygons = 0
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            keyword = parts[0]
            if keyword == "v":
                if len(parts) < 4:
                    raise ReaderError(f"OBJ reader: line {number} has an incomplete vertex")
                try:
                    coords = [float(parts[1]), float(parts[2]), float(parts[3])]
                    if len(parts) >= 5:
                        weight = float(parts[4])
                        if weight == 0.0:
                            raise ValueError("zero homogeneous weight")
                        coords = [value / weight for value in coords]
                except ValueError as exc:
                    raise ReaderError(
                        f"OBJ reader: line {number} has invalid vertex values: {exc}"
                    ) from exc
                vertices.append(coords)
            elif keyword == "f":
                corners = []
                for token in parts[1:]:
                    head = token.split("/")[0]
                    try:
                        index = int(head)
                    except ValueError as exc:
                        raise ReaderError(
                            f"OBJ reader: line {number} has invalid face index {token!r}"
                        ) from exc
                    if index == 0:
                        raise ReaderError(f"OBJ reader: line {number} uses index 0")
                    if index < 0:
                        index = len(vertices) + index
                    else:
                        index -= 1
                    if index < 0 or index >= len(vertices):
                        raise ReaderError(
                            f"OBJ reader: line {number} references vertex {token!r} "
                            f"but only {len(vertices)} vertices are defined"
                        )
                    corners.append(index)
                if len(corners) < 3:
                    raise ReaderError(
                        f"OBJ reader: line {number} has fewer than three face vertices"
                    )
                if len(corners) == 3:
                    faces.append(corners)
                elif triangulate:
                    polygons += 1
                    for position in range(1, len(corners) - 1):
                        faces.append([corners[0], corners[position], corners[position + 1]])
                else:
                    raise ReaderError(
                        f"OBJ reader: line {number} is a polygon with {len(corners)} "
                        "vertices; set triangulate=true to fan-triangulate it"
                    )
                if len(faces) > max_faces:
                    raise ReaderError(f"OBJ reader: more than max_faces={max_faces} faces")
            elif keyword == "o":
                if len(parts) > 1:
                    objects.append(" ".join(parts[1:]))
        if not vertices:
            raise ReaderError("OBJ reader: file has no vertices")
        if not faces:
            raise ReaderError("OBJ reader: file has no faces")
        n_vertices = len(vertices)
        n_faces = len(faces)
        data = np.full((n_vertices + n_faces, 6), np.nan, dtype=np.float64)
        data[:n_vertices, :3] = np.asarray(vertices, dtype=np.float64)
        data[n_vertices:, 3:] = np.asarray(faces, dtype=np.float64)
        names = [f"vertex{i}" for i in range(n_vertices)] + [
            f"face{j}" for j in range(n_faces)]
        out = Form(
            data=compact_numeric(data),
            dims=[element_dim, field_dim],
            labels={element_dim: unique_labels(names, element_dim, "obj"),
                    field_dim: {name: i for i, name in enumerate(_FIELDS)}},
            info={"missing_code": np.nan, "format": "obj", "n_vertices": int(n_vertices),
                  "n_faces": int(n_faces), "triangulated": bool(triangulate),
                  "polygons": int(polygons), "objects": objects},
        )
        out.validate()
        return out
