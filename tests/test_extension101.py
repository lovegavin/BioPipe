"""Tests for the 1.16.0 bioenv, Morisita and volume reader additions."""
from __future__ import annotations


import numpy as np
import pytest

from src.core import Form, ReaderError, StepError
from src.reader import pick_reader
from src.reader.readers.nifti_reader import NiftiReader
from src.reader.readers.nrrd_reader import NrrdReader
from src.task.step.steps.bioenv import BioenvStep
from src.task.step.steps.morisita import MorisitaStep

COMMUNITY = np.asarray([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=np.float64)

ENV = np.asarray([
    [1.234, 5.217, 0.201],
    [2.591, 7.903, 0.374],
    [4.113, 3.411, 0.618],
    [6.702, 2.098, 1.027],
    [8.319, 1.612, 1.639],
    [11.427, 0.407, 2.751],
], dtype=np.float64)

MORISITA = np.asarray([
    [5, 0, 2],
    [3, 1, 0],
    [0, 4, 1],
    [2, 2, 3],
    [1, 3, 0],
], dtype=np.float64)

BIOENV_RHO = [0.50358746411968947, 0.44623942550107709, 0.40860477515761273]
BIOENV_VARIABLES = [["x"], ["x", "z"], ["x", "y", "z"]]
MORISITA_VALUES = np.asarray([
    [1.2727272727272725, 1.7143286781877798, 0.64844185570879298,
     0.190897608520470913, 0.15102186889614769],
    [1.1111111111111112, 1.7936985313197553, 0.60937983967643672,
     0.069995789790839438, 0.28729749518364578],
    [1.3333333333333333, 2.4286573563755596, 0.29688371141758607,
     0.116659649651398981, 0.22546314129598133],
])


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float64), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _community_form():
    samples = {f"s{i}": i for i in range(COMMUNITY.shape[0])}
    taxa = {f"t{i}": i for i in range(COMMUNITY.shape[1])}
    return _form(COMMUNITY, ["sample", "taxon"], {"sample": samples, "taxon": taxa})


def _env_form(matrix=None, names=("x", "y", "z")):
    matrix = ENV if matrix is None else matrix
    samples = {f"s{i}": i for i in range(matrix.shape[0])}
    env = {name: i for i, name in enumerate(names)}
    return _form(matrix, ["sample", "env"], {"sample": samples, "env": env})


def _morisita_form(matrix=None):
    matrix = MORISITA if matrix is None else matrix
    samples = {f"s{i}": i for i in range(matrix.shape[0])}
    features = {f"sp{i}": i for i in range(matrix.shape[1])}
    return _form(matrix, ["sample", "feature"],
                 {"sample": samples, "feature": features})


def test_bioenv_matches_vegan():
    out, export = _run(BioenvStep(), (_community_form(), _env_form()))
    assert out.dims == ["size", "statistic"]
    assert out.labels["size"] == {"1": 0, "2": 1, "3": 2}
    np.testing.assert_allclose(out.data[:, 0], BIOENV_RHO, rtol=1e-6, atol=1e-7)
    models = out.info["models"]
    assert [model["variables"] for model in models] == BIOENV_VARIABLES
    assert export["best_size"] == 1
    assert export["best_variables"] == ["x"]
    assert export["best_rho"] == pytest.approx(BIOENV_RHO[0], rel=1e-6)


def test_bioenv_upto_and_constant_columns():
    env = np.column_stack([ENV, np.full(ENV.shape[0], 3.5)])
    form = _env_form(env, names=("x", "y", "z", "const"))
    out, _ = _run(BioenvStep(), (_community_form(), form), {"upto": 1})
    assert out.info["dropped_constant"] == ["const"]
    assert out.info["n_env"] == 3
    assert out.labels["size"] == {"1": 0}
    with pytest.raises(StepError, match="all environment variables are constant"):
        _run(BioenvStep(), (_community_form(),
                            _env_form(np.full_like(ENV, 2.0))),
             {"upto": 1})


def test_bioenv_rejects_mismatched_samples():
    form = _env_form()
    labels = dict(form.labels["sample"])
    labels["s9"] = 0
    broken = Form(data=form.data, dims=form.dims,
                  labels={"sample": labels, "env": form.labels["env"]},
                  info=form.info)
    with pytest.raises(StepError, match="same sample labels"):
        _run(BioenvStep(), (_community_form(), broken))


def test_morisita_matches_vegan():
    out, export = _run(MorisitaStep(), (_morisita_form(),))
    assert out.dims == ["feature", "statistic"]
    assert out.labels["statistic"] == {"imor": 0, "mclu": 1, "muni": 2,
                                       "imst": 3, "pchisq": 4}
    np.testing.assert_allclose(out.data, MORISITA_VALUES, rtol=1e-6, atol=1e-7)
    assert export["n_features"] == 3


def test_morisita_unique_and_skipped_features():
    matrix = np.column_stack([MORISITA, [5, 0, 0, 0, 0], [1, 0, 0, 0, 0]])
    form = _form(matrix, ["sample", "feature"],
                 {"sample": {f"s{i}": i for i in range(matrix.shape[0])},
                  "feature": {f"sp{i}": i for i in range(matrix.shape[1])}})
    out, _ = _run(MorisitaStep(), (form,), {"unique_rm": True})
    assert out.info["removed"] == ["sp3", "sp4"]
    assert list(out.labels["feature"]) == ["sp0", "sp1", "sp2"]
    out, _ = _run(MorisitaStep(), (form,))
    assert "sp4" in out.info["skipped"]
    row = out.labels["feature"]["sp4"]
    assert np.all(np.isnan(out.data[row]))
    with pytest.raises(StepError, match="crit"):
        _run(MorisitaStep(), (_morisita_form(),), {"crit": 0.0})


def test_nifti_reader_matches_nibabel(tmp_path):
    nib = pytest.importorskip("nibabel")
    data = np.arange(24, dtype=np.int16).reshape(4, 3, 2) * 3 - 7
    affine = np.asarray([[2.0, 0, 0, 10.0], [0, 2.5, 0, -5.0],
                         [0, 0, 3.0, 7.0], [0, 0, 0, 1.0]])
    image = nib.Nifti1Image(data, affine)
    image.header.set_data_dtype(np.int16)
    image.header.set_slope_inter(2.0, -1.0)
    path = tmp_path / "volume.nii"
    nib.save(image, str(path))
    form = NiftiReader().read(path, ["slice", "voxel"],
                              {"slice": "auto", "voxel": "builtin"})
    expected = nib.load(str(path)).get_fdata().transpose(2, 1, 0).reshape(2, 12)
    np.testing.assert_allclose(form.data, expected, atol=1e-6)
    np.testing.assert_allclose(form.info["voxel_size"], [2.0, 2.5, 3.0], atol=1e-9)
    np.testing.assert_allclose(form.info["affine"], image.affine, atol=1e-9)
    assert form.info["scl_slope"] == 2.0
    assert form.info["scl_inter"] == -1.0
    assert form.info["scaled"] is True
    sliced = NiftiReader().read(path, ["slice", "voxel"],
                                {"slice": "auto", "voxel": "builtin"},
                                slice_start=1)
    assert sliced.data.shape == (1, 12)
    np.testing.assert_allclose(sliced.data[0], expected[1], atol=1e-6)
    with pytest.raises(ReaderError, match="slice range"):
        NiftiReader().read(path, ["slice", "voxel"],
                           {"slice": "auto", "voxel": "builtin"}, slice_stop=5)


def test_nifti_compressed_and_errors(tmp_path):
    nib = pytest.importorskip("nibabel")
    data = np.arange(12, dtype=np.float32).reshape(3, 2, 2)
    image = nib.Nifti1Image(data, np.eye(4))
    gz = tmp_path / "volume.nii.gz"
    nib.save(image, str(gz))
    plain = tmp_path / "volume.nii"
    nib.save(image, str(plain))
    assert isinstance(pick_reader(gz).implementation(), NiftiReader)
    from src.reader import read_source
    form = read_source(gz, ["slice", "voxel"],
                       {"slice": "auto", "voxel": "builtin"})
    expected = image.get_fdata().transpose(2, 1, 0).reshape(2, 6)
    np.testing.assert_allclose(form.data, expected, atol=1e-6)
    raw = plain.read_bytes()
    truncated = tmp_path / "truncated.nii"
    truncated.write_bytes(raw[:380])
    with pytest.raises(ReaderError, match="header describes"):
        NiftiReader().read(truncated, ["slice", "voxel"],
                           {"slice": "auto", "voxel": "builtin"})
    bad = tmp_path / "bad.nii"
    bad.write_bytes(b"\x00" * 400)
    with pytest.raises(ReaderError, match="sizeof_hdr"):
        NiftiReader().read(bad, ["slice", "voxel"],
                           {"slice": "auto", "voxel": "builtin"})


def test_nrrd_reader_matches_pynrrd(tmp_path):
    nrrd = pytest.importorskip("nrrd")
    array = np.arange(24, dtype=np.float32).reshape(2, 3, 4) * 0.5
    header = {"type": "float", "dimension": 3, "sizes": [4, 3, 2],
              "encoding": "gzip",
              "space directions": [[2, 0, 0], [0, 3, 0], [0, 0, 4]],
              "space origin": [1, 2, 3],
              "kinds": ["domain", "domain", "domain"]}
    path = tmp_path / "volume.nrrd"
    nrrd.write(str(path), np.ascontiguousarray(array.T), header=header)
    back, _ = nrrd.read(str(path))
    form = NrrdReader().read(path, ["slice", "voxel"],
                             {"slice": "auto", "voxel": "builtin"})
    expected = np.asarray(back).transpose(2, 1, 0).reshape(2, 12)
    np.testing.assert_allclose(form.data, expected, atol=1e-6)
    assert form.info["encoding"] == "gzip"
    assert form.info["sizes"] == [4, 3, 2]
    np.testing.assert_allclose(np.asarray(form.info["affine"])[:3, :3],
                               np.diag([2.0, 3.0, 4.0]))
    np.testing.assert_allclose(np.asarray(form.info["affine"])[:3, 3], [1, 2, 3])


def test_nrrd_big_endian_2d_and_errors(tmp_path):
    values = np.asarray([[1, 2, 3], [4, 5, 6]], dtype=np.uint16)
    header = ("NRRD0004\ntype: ushort\nendian: big\ndimension: 2\n"
              "sizes: 3 2\nencoding: raw\n\n")
    path = tmp_path / "manual.nrrd"
    path.write_bytes(header.encode("ascii") + values.astype(">u2").tobytes())
    form = NrrdReader().read(path, ["slice", "voxel"],
                             {"slice": "auto", "voxel": "builtin"})
    assert form.data.shape == (1, 6)
    np.testing.assert_allclose(form.data[0], [1, 2, 3, 4, 5, 6])
    assert form.info["byte_order"] == "big"
    bad = tmp_path / "bad.nrrd"
    bad.write_bytes(b"NOTNRRD\n\n")
    with pytest.raises(ReaderError, match="magic"):
        NrrdReader().read(bad, ["slice", "voxel"],
                          {"slice": "auto", "voxel": "builtin"})
    four = tmp_path / "four.nrrd"
    four.write_bytes(b"NRRD0004\ntype: float\ndimension: 4\nsizes: 2 2 2 2\n"
                     b"encoding: raw\n\n" + b"\x00" * 16 * 4)
    with pytest.raises(ReaderError, match="2-D and 3-D"):
        NrrdReader().read(four, ["slice", "voxel"],
                          {"slice": "auto", "voxel": "builtin"})
