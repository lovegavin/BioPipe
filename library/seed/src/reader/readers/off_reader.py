"""Object File Format (OFF) ASCII mesh reader."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels

_FIELDS = ["x", "y", "z", "v0", "v1", "v2"]
_VARIANTS = {"OFF", "COFF", "NOFF", "CNOFF", "STOFF"}


def _logical_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        cut = line.split("#", 1)[0].strip()
        if cut:
            lines.append(cut)
    return lines


class OffReader(Reader):
    provider = 'operon-readers'
    """Parse an ASCII OFF polygon mesh into an element x field table."""
    parameters_file = 'off_reader.OffReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'OffReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Read an OFF polygon mesh',
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
     'description': ('Read an ASCII OFF (Object File Format) polygon mesh as one table: '
                     'vertex rows carry x/y/z and face rows carry three vertex indices.'),
     'extensions': ['.off'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['element', 'field'],
                    'labels': {'element': 'auto', 'field': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        path = Path(path)
        if len(dims) != 2:
            raise ReaderError(f"OFF reader requires exactly two dims, got {dims}")
        element_dim, field_dim = dims
        triangulate = bool(args.get("triangulate", True))
        max_faces = int(args.get("max_faces") or 1000000)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ReaderError(f"OFF reader: cannot read {path}: {exc}") from exc
        if not raw:
            raise ReaderError("OFF reader: file is empty")
        if b"\x00" in raw:
            raise ReaderError("OFF reader: only ASCII OFF is supported")
        lines = _logical_lines(raw.decode("utf-8", "replace"))
        if not lines:
            raise ReaderError("OFF reader: file has no content")
        header = lines[0].split()
        if not header or header[0] not in _VARIANTS:
            raise ReaderError(f"OFF reader: expected an OFF header, got {lines[0]!r}")
        variant = header[0]
        counts: list[str] = header[1:]
        cursor = 1
        if not counts:
            if len(lines) < 2:
                raise ReaderError("OFF reader: missing vertex/face counts")
            counts = lines[1].split()
            cursor = 2
        if len(counts) < 3:
            raise ReaderError("OFF reader: counts line needs three integers")
        try:
            n_vertices, n_faces, _n_edges = (int(value) for value in counts[:3])
        except ValueError as exc:
            raise ReaderError(f"OFF reader: invalid counts {counts[:3]!r}") from exc
        if n_vertices <= 0:
            raise ReaderError("OFF reader: vertex count must be positive")
        if n_faces < 0:
            raise ReaderError("OFF reader: face count must be non-negative")
        if cursor + n_vertices + n_faces > len(lines):
            raise ReaderError(
                f"OFF reader: file declares {n_vertices} vertices and {n_faces} faces "
                "but has too few lines")
        vertices = np.empty((n_vertices, 3), dtype=np.float64)
        for row in range(n_vertices):
            parts = lines[cursor + row].split()
            if len(parts) < 3:
                raise ReaderError(
                    f"OFF reader: vertex line {cursor + row + 1} has fewer than three values")
            try:
                vertices[row] = [float(parts[0]), float(parts[1]), float(parts[2])]
            except ValueError as exc:
                raise ReaderError(
                    f"OFF reader: invalid vertex values on line {cursor + row + 1}") from exc
        face_start = cursor + n_vertices
        triangles: list[list[int]] = []
        polygons = 0
        for row in range(n_faces):
            parts = lines[face_start + row].split()
            if not parts:
                raise ReaderError(f"OFF reader: empty face line {face_start + row + 1}")
            try:
                count = int(parts[0])
            except ValueError as exc:
                raise ReaderError(
                    f"OFF reader: invalid face size on line {face_start + row + 1}") from exc
            if count < 3:
                raise ReaderError(
                    f"OFF reader: face on line {face_start + row + 1} has fewer than three vertices")
            if len(parts) < count + 1:
                raise ReaderError(
                    f"OFF reader: face on line {face_start + row + 1} is truncated")
            try:
                corners = [int(value) for value in parts[1:count + 1]]
            except ValueError as exc:
                raise ReaderError(
                    f"OFF reader: non-integer face index on line {face_start + row + 1}") from exc
            if any(index < 0 or index >= n_vertices for index in corners):
                raise ReaderError(
                    f"OFF reader: face on line {face_start + row + 1} references a vertex "
                    "outside the declared range")
            if count == 3:
                triangles.append(corners)
            elif not triangulate:
                raise ReaderError("OFF reader: polygon faces need triangulate=true")
            else:
                polygons += 1
                for position in range(1, count - 1):
                    triangles.append([corners[0], corners[position], corners[position + 1]])
            if len(triangles) > max_faces:
                raise ReaderError(f"OFF reader: more than max_faces={max_faces} faces")
        face_array = np.asarray(triangles, dtype=np.int64).reshape(-1, 3)
        n_faces_out = face_array.shape[0]
        data = np.full((n_vertices + n_faces_out, 6), np.nan, dtype=np.float64)
        data[:n_vertices, :3] = vertices
        data[n_vertices:, 3:] = face_array
        names = [f"vertex{i}" for i in range(n_vertices)] + [
            f"face{j}" for j in range(n_faces_out)]
        out = Form(
            data=compact_numeric(data),
            dims=[element_dim, field_dim],
            labels={element_dim: unique_labels(names, element_dim, "off"),
                    field_dim: {name: i for i, name in enumerate(_FIELDS)}},
            info={
                "missing_code": np.nan,
                "format": "ascii",
                "variant": variant,
                "n_vertices": int(n_vertices),
                "n_faces": int(n_faces_out),
                "polygons": int(polygons),
                "triangulated": bool(triangulate),
            },
        )
        out.validate()
        return out
