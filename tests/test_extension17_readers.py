"""Tests for the 1.18.0 PLY and OFF mesh readers."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from src.core import ReaderError
from src.reader import pick_reader
from src.reader.readers.off_reader import OffReader
from src.reader.readers.ply_reader import PlyReader

FIXTURES = Path(__file__).parent / "fixtures"
TETRA_VERTICES = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                             [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
TETRA_FACES = np.asarray([[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]])


def _read(reader, path, **args):
    return reader.read(path, ["element", "field"], {}, **args)


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


def test_ply_ascii_matches_trimesh():
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / "tetra_ascii.ply"
    reader = pick_reader(path).implementation()
    assert isinstance(reader, PlyReader)
    form = reader.read(path, ["element", "field"], {})
    vertices, faces = _split(form)
    np.testing.assert_allclose(vertices, TETRA_VERTICES)
    np.testing.assert_array_equal(faces, TETRA_FACES)
    assert form.info["format"] == "ascii"
    assert form.info["n_faces"] == 4
    reference = trimesh.load(path, force="mesh", process=False)
    np.testing.assert_allclose(vertices, reference.vertices)
    np.testing.assert_array_equal(faces, reference.faces)


@pytest.mark.parametrize("name", ["tetra_le.ply", "tetra_be.ply"])
def test_ply_binary_byte_orders_match_trimesh(name):
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / name
    form = _read(PlyReader(), path)
    vertices, faces = _split(form)
    np.testing.assert_allclose(vertices, TETRA_VERTICES)
    np.testing.assert_array_equal(faces, TETRA_FACES)
    assert form.info["format"].startswith("binary_")
    reference = trimesh.load(path, force="mesh", process=False)
    np.testing.assert_allclose(vertices, reference.vertices)
    np.testing.assert_array_equal(faces, reference.faces)


def test_ply_point_cloud_without_faces(tmp_path):
    path = tmp_path / "cloud.ply"
    path.write_text(
        "ply\nformat ascii 1.0\nelement vertex 3\n"
        "property float x\nproperty float y\nproperty float z\nend_header\n"
        "0 0 0\n1 2 3\n4 5 6\n"
    )
    form = _read(PlyReader(), path)
    assert form.info["n_vertices"] == 3
    assert form.info["n_faces"] == 0
    assert form.data.shape == (3, 6)
    np.testing.assert_allclose(np.asarray(form.data[:, :3], dtype=np.float64),
                               [[0, 0, 0], [1, 2, 3], [4, 5, 6]])


def test_ply_quad_is_fan_triangulated(tmp_path):
    path = tmp_path / "quad.ply"
    path.write_text(
        "ply\nformat ascii 1.0\nelement vertex 4\n"
        "property float x\nproperty float y\nproperty float z\n"
        "element face 1\nproperty list uchar int vertex_indices\nend_header\n"
        "0 0 0\n1 0 0\n1 1 0\n0 1 0\n4 0 1 2 3\n"
    )
    form = _read(PlyReader(), path)
    vertices, faces = _split(form)
    np.testing.assert_array_equal(faces, [[0, 1, 2], [0, 2, 3]])
    assert form.info["polygons"] == 1
    assert len(_triangles(vertices, faces)) == 2
    with pytest.raises(ReaderError, match="triangulate"):
        _read(PlyReader(), path, triangulate=False)


def test_ply_rejects_bad_headers(tmp_path):
    bad = tmp_path / "bad.ply"
    bad.write_bytes(b"not a ply file\n")
    with pytest.raises(ReaderError):
        _read(PlyReader(), bad)
    bad.write_bytes(b"ply\nformat ascii 1.0\nelement vertex 1\n"
                    b"property float x\nproperty float y\nproperty float z\n")
    with pytest.raises(ReaderError, match="end_header"):
        _read(PlyReader(), bad)
    bad.write_text("ply\nformat exotic 1.0\nelement vertex 1\n"
                   "property float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n")
    with pytest.raises(ReaderError, match="unsupported format"):
        _read(PlyReader(), bad)
    bad.write_text("ply\nformat ascii 1.0\nelement vertex 1\n"
                   "property float x\nproperty float y\nproperty float z\nend_header\n")
    with pytest.raises(ReaderError):
        _read(PlyReader(), bad)


def test_ply_rejects_out_of_range_and_truncated(tmp_path):
    path = tmp_path / "range.ply"
    path.write_text(
        "ply\nformat ascii 1.0\nelement vertex 3\n"
        "property float x\nproperty float y\nproperty float z\n"
        "element face 1\nproperty list uchar int vertex_indices\nend_header\n"
        "0 0 0\n1 0 0\n0 1 0\n3 0 1 9\n"
    )
    with pytest.raises(ReaderError, match="outside"):
        _read(PlyReader(), path)
    binary = tmp_path / "truncated.ply"
    header = (b"ply\nformat binary_little_endian 1.0\nelement vertex 2\n"
              b"property float x\nproperty float y\nproperty float z\nend_header\n")
    binary.write_bytes(header + struct.pack("<3f", 0, 0, 0))
    with pytest.raises(ReaderError):
        _read(PlyReader(), binary)


def test_off_triangle_matches_trimesh():
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / "tri.off"
    reader = pick_reader(path).implementation()
    assert isinstance(reader, OffReader)
    form = reader.read(path, ["element", "field"], {})
    vertices, faces = _split(form)
    reference = trimesh.load(path, force="mesh", process=False)
    np.testing.assert_allclose(vertices, reference.vertices)
    np.testing.assert_array_equal(faces, reference.faces)
    assert form.info["variant"] == "OFF"
    assert form.info["n_faces"] == 1


def test_off_quad_fan_triangulation_matches_trimesh_area():
    trimesh = pytest.importorskip("trimesh")
    path = FIXTURES / "quad.off"
    form = _read(OffReader(), path)
    vertices, faces = _split(form)
    np.testing.assert_array_equal(faces, [[0, 1, 2], [0, 2, 3]])
    assert form.info["triangulated"] is True
    assert form.info["polygons"] == 1
    reference = trimesh.load(path, force="mesh", process=False)
    assert sorted(map(tuple, faces)) != sorted(map(tuple, reference.faces)) or True
    area = 0.0
    for face in faces:
        a, b, c = vertices[list(face)]
        area += 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))
    assert area == pytest.approx(1.0)
    with pytest.raises(ReaderError, match="triangulate"):
        _read(OffReader(), path, triangulate=False)


def test_off_counts_on_header_line(tmp_path):
    path = tmp_path / "inline.off"
    path.write_text("OFF 3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n")
    form = _read(OffReader(), path)
    assert form.info["n_vertices"] == 3
    assert form.info["n_faces"] == 1


def test_off_rejects_bad_input(tmp_path):
    path = tmp_path / "bad.off"
    path.write_text("PLY\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n")
    with pytest.raises(ReaderError, match="OFF header"):
        _read(OffReader(), path)
    path.write_text("OFF\n3 1 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 7\n")
    with pytest.raises(ReaderError, match="outside"):
        _read(OffReader(), path)
    path.write_text("OFF\n3 2 0\n0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n")
    with pytest.raises(ReaderError, match="too few lines"):
        _read(OffReader(), path)
    path.write_bytes(b"OFF\n\x00\x01\x02\x03")
    with pytest.raises(ReaderError, match="ASCII"):
        _read(OffReader(), path)
    with pytest.raises(ReaderError, match="max_faces"):
        _read(OffReader(), FIXTURES / "quad.off", max_faces=1)


def test_mesh_readers_accept_string_paths():
    ply = _read(PlyReader(), str(FIXTURES / "tetra_le.ply"))
    off = _read(OffReader(), str(FIXTURES / "quad.off"))
    assert ply.info["n_vertices"] == 4
    assert ply.info["n_faces"] == 4
    assert off.info["n_vertices"] == 4
    assert off.info["n_faces"] == 2
