"""Tests for the 1.17.0 STL and OBJ mesh readers."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from src.core import ReaderError
from src.reader import pick_reader
from src.reader.readers.obj_reader import ObjReader
from src.reader.readers.stl_reader import StlReader

FIXTURES = Path(__file__).parent / "fixtures"
TETRA_VERTICES = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                             [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
TETRA_FACES = np.asarray([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])


def _read(path, **args):
    return StlReader().read(path, ["element", "field"], {}, **args)


def _split(form):
    n_vertices = form.info["n_vertices"]
    vertices = np.asarray(form.data[:n_vertices, :3], dtype=np.float64)
    faces = np.asarray(form.data[n_vertices:, 3:], dtype=np.int64)
    return vertices, faces


def _triangles(vertices, faces):
    result = []
    for face in faces:
        triangle = tuple(sorted(tuple(np.round(vertices[index], 6)) for index in face))
        result.append(triangle)
    return sorted(result)


def test_stl_binary_matches_trimesh():
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / "tetra.stl"
    reader = pick_reader(path).implementation()
    assert isinstance(reader, StlReader)
    form = reader.read(path, ["element", "field"], {})
    assert form.dims == ["element", "field"]
    assert list(form.labels["field"]) == ["x", "y", "z", "v0", "v1", "v2"]
    assert form.info["format"] == "binary"
    assert form.info["n_vertices"] == 4
    assert form.info["n_faces"] == 4
    vertices, faces = _split(form)
    np.testing.assert_allclose(np.sort(vertices, axis=0),
                               np.sort(TETRA_VERTICES, axis=0), atol=1e-6)
    mesh = trimesh.load(path, force="mesh", process=False)
    assert form.info["n_faces"] == len(mesh.faces)
    assert _triangles(vertices, faces) == _triangles(mesh.vertices, mesh.faces)


def test_stl_ascii_matches_binary():
    form = _read(FIXTURES / "tetra_ascii.stl")
    assert form.info["format"] == "ascii"
    assert form.info["n_vertices"] == 4
    assert form.info["n_faces"] == 4
    vertices, faces = _split(form)
    np.testing.assert_allclose(np.sort(vertices, axis=0),
                               np.sort(TETRA_VERTICES, axis=0), atol=1e-6)
    assert _triangles(vertices, faces) == _triangles(TETRA_VERTICES, TETRA_FACES)


def test_stl_without_merging_keeps_corner_vertices():
    form = _read(FIXTURES / "tetra.stl", merge_vertices=False)
    assert form.info["n_vertices"] == 12
    assert form.info["n_faces"] == 4
    vertices, faces = _split(form)
    assert faces.shape == (4, 3)
    assert vertices.shape == (12, 3)


def test_stl_errors(tmp_path):
    truncated = tmp_path / "truncated.stl"
    truncated.write_bytes(b"\x00" * 80 + struct.pack("<I", 5) + b"\x00" * 50)
    with pytest.raises(ReaderError, match="neither a valid binary nor ASCII STL"):
        _read(truncated)
    empty = tmp_path / "empty.stl"
    empty.write_bytes(b"")
    with pytest.raises(ReaderError, match="file is empty"):
        _read(empty)
    with pytest.raises(ReaderError, match="max_faces"):
        _read(FIXTURES / "tetra.stl", max_faces=2)
    broken = tmp_path / "broken.stl"
    broken.write_text("solid x\n facet normal 0 0 0\n vertex 0 0\n endsolid x\n",
                      encoding="utf-8")
    with pytest.raises(ReaderError, match="malformed vertex|facets but"):
        _read(broken)


def test_obj_matches_trimesh_and_negative_indices():
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / "tetra.obj"
    reader = pick_reader(path).implementation()
    assert isinstance(reader, ObjReader)
    form = reader.read(path, ["element", "field"], {})
    assert form.info["format"] == "obj"
    assert form.info["n_vertices"] == 4
    assert form.info["n_faces"] == 4
    vertices, faces = _split(form)
    np.testing.assert_allclose(vertices, TETRA_VERTICES, atol=1e-6)
    np.testing.assert_array_equal(faces, TETRA_FACES)
    mesh = trimesh.load(path, force="mesh", process=False)
    assert _triangles(vertices, faces) == _triangles(mesh.vertices, mesh.faces)


def test_obj_polygon_triangulation():
    path = FIXTURES / "quad.obj"
    form = ObjReader().read(path, ["element", "field"], {})
    vertices, faces = _split(form)
    np.testing.assert_array_equal(faces, [[0, 1, 2], [0, 2, 3]])
    assert {int(index) for face in faces for index in face} == {0, 1, 2, 3}
    assert form.info["polygons"] == 1
    with pytest.raises(ReaderError, match="triangulate=true"):
        ObjReader().read(path, ["element", "field"], {}, triangulate=False)


def test_obj_errors(tmp_path):
    bad = tmp_path / "bad.obj"
    bad.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 9\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="references vertex"):
        ObjReader().read(bad, ["element", "field"], {})
    zero = tmp_path / "zero.obj"
    zero.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 0\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="index 0"):
        ObjReader().read(zero, ["element", "field"], {})
    no_faces = tmp_path / "no_faces.obj"
    no_faces.write_text("v 0 0 0\nv 1 0 0\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="no faces"):
        ObjReader().read(no_faces, ["element", "field"], {})
    with pytest.raises(ReaderError, match="max_faces"):
        ObjReader().read(FIXTURES / "tetra.obj", ["element", "field"], {},
                         max_faces=2)
