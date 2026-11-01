"""Tests for the 1.15.0 beta-diversity, Tsallis, varpart and MRC additions."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import Form, ReaderError, StepError
from src.reader.readers.mrc_reader import MrcReader
from src.task.step.steps.betadiver import METHODS, BetadiverStep
from src.task.step.steps.tsallis import TsallisStep
from src.task.step.steps.varpart import VarpartStep

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "tiny.mrc"

ABUNDANCE = np.asarray([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=np.float64)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _form(data, dims, labels, info=None):
    form = Form(data=np.asarray(data, dtype=np.float32), dims=list(dims),
                labels=labels, info=info or {"missing_code": np.nan})
    form.validate()
    return form


def _abundance_form():
    samples = {f"s{i}": i for i in range(ABUNDANCE.shape[0])}
    taxa = {f"t{i}": i for i in range(ABUNDANCE.shape[1])}
    return _form(ABUNDANCE, ["sample", "taxon"],
                 {"sample": samples, "taxon": taxa})


def _presence():
    return (ABUNDANCE > 0).astype(float)


def test_betadiver_hand_computed_pairs():
    out, export = _run(BetadiverStep(), (_abundance_form(),), {"method": "w"})
    assert export["method"] == "w"
    assert out.dims == ["sample", "sample_b"]
    label = out.labels["sample"]
    matrix = out.data
    np.testing.assert_allclose(np.diag(matrix), 0.0, atol=1e-6)
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-6)
    # s0 {t0,t1,t3} vs s1 {t0,t1,t2}: a=2, b=1, c=1.
    assert matrix[label["s0"], label["s1"]] == pytest.approx(1.0 / 3.0, abs=1e-6)
    # s0 vs s2 {t0,t3}: a=2, b=1, c=0.
    assert matrix[label["s0"], label["s2"]] == pytest.approx(0.2, abs=1e-6)
    out_c, _ = _run(BetadiverStep(), (_abundance_form(),), {"method": "c"})
    assert out_c.data[label["s0"], label["s1"]] == pytest.approx(1.0, abs=1e-6)
    out_j, _ = _run(BetadiverStep(), (_abundance_form(),), {"method": "j"})
    assert out_j.data[label["s0"], label["s1"]] == pytest.approx(0.5, abs=1e-6)
    out_sor, _ = _run(BetadiverStep(), (_abundance_form(),), {"method": "sor"})
    assert out_sor.data[label["s0"], label["s1"]] == pytest.approx(4.0 / 6.0, abs=1e-6)
    out_gl, _ = _run(BetadiverStep(), (_abundance_form(),), {"method": "gl"})
    assert out_gl.data[label["s0"], label["s1"]] == pytest.approx(0.0, abs=1e-6)
    assert out_gl.data[label["s0"], label["s2"]] == pytest.approx(0.4, abs=1e-6)


def test_betadiver_all_methods_are_symmetric():
    form = _abundance_form()
    samples = len(ABUNDANCE)
    for method in METHODS:
        out, _ = _run(BetadiverStep(), (form,), {"method": method})
        assert out.data.shape == (samples, samples)
        np.testing.assert_allclose(np.diag(out.data), 0.0, atol=1e-6)
        np.testing.assert_allclose(out.data, out.data.T, atol=1e-6)
        assert np.all(np.isfinite(out.data))


def test_betadiver_rejects_unknown_method():
    with pytest.raises(StepError, match="unknown method"):
        _run(BetadiverStep(), (_abundance_form(),), {"method": "nope"})


def test_betadiver_rejects_negative_abundance():
    data = ABUNDANCE.copy()
    data[0, 0] = -1.0
    form = _form(data, ["sample", "taxon"],
                 {"sample": {f"s{i}": i for i in range(6)},
                  "taxon": {f"t{i}": i for i in range(4)}})
    with pytest.raises(StepError, match="non-negative"):
        _run(BetadiverStep(), (form,), {})


def test_tsallis_orders_hand_computed():
    out, export = _run(TsallisStep(), (_abundance_form(),),
                       {"scales": [0, 1, 2]})
    assert out.dims == ["sample", "scale"]
    assert list(out.labels["scale"]) == ["0", "1", "2"]
    assert export["scales"] == ["0", "1", "2"]
    sizes = np.count_nonzero(ABUNDANCE > 0, axis=1)
    np.testing.assert_allclose(out.data[:, 0], sizes - 1.0, atol=1e-6)
    p = ABUNDANCE / ABUNDANCE.sum(axis=1, keepdims=True)
    positive = p > 0
    clr = np.where(positive, p * np.log(np.where(positive, p, 1.0)), 0.0)
    np.testing.assert_allclose(out.data[:, 1], -clr.sum(axis=1), rtol=1e-6, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], 1.0 - (p ** 2).sum(axis=1),
                               rtol=1e-6, atol=1e-6)


def test_tsallis_hill_numbers():
    out, _ = _run(TsallisStep(), (_abundance_form(),),
                  {"scales": [0, 2], "hill": True})
    sizes = np.count_nonzero(ABUNDANCE > 0, axis=1)
    np.testing.assert_allclose(out.data[:, 0], sizes, atol=1e-6)
    p = ABUNDANCE / ABUNDANCE.sum(axis=1, keepdims=True)
    np.testing.assert_allclose(out.data[:, 1], 1.0 / (p ** 2).sum(axis=1),
                               rtol=1e-6, atol=1e-6)


def test_tsallis_norm_prefers_uniform_profile():
    out, _ = _run(TsallisStep(), (_abundance_form(),),
                  {"scales": [0], "norm": True})
    np.testing.assert_allclose(out.data[:, 0], 1.0, atol=1e-6)


def test_tsallis_rejects_norm_with_hill():
    with pytest.raises(StepError, match="cannot be enabled together"):
        _run(TsallisStep(), (_abundance_form(),), {"norm": True, "hill": True})


def test_tsallis_zero_sample_is_missing():
    data = ABUNDANCE.copy()
    data[2, :] = 0.0
    form = _form(data, ["sample", "taxon"],
                 {"sample": {f"s{i}": i for i in range(6)},
                  "taxon": {f"t{i}": i for i in range(4)}})
    out, _ = _run(TsallisStep(), (form,), {"scales": [1]})
    assert out.info["zero_samples"] == 1
    assert np.isnan(out.data[2, 0])


def _varpart_inputs(seed=20261102, n=24):
    rng = np.random.default_rng(seed)
    samples = {f"s{i}": i for i in range(n)}
    response = rng.normal(size=(n, 3))
    first = rng.normal(size=(n, 2))
    second = 0.4 * first + rng.normal(size=(n, 2))
    y = _form(response, ["sample", "response"],
              {"sample": samples, "response": {"y0": 0, "y1": 1, "y2": 2}})
    x1 = _form(first, ["sample", "predictor"],
               {"sample": samples, "predictor": {"p0": 0, "p1": 1}})
    x2 = _form(second, ["sample", "predictor_b"],
               {"sample": samples, "predictor_b": {"q0": 0, "q1": 1}})
    return y, x1, x2, response, first, second


def test_varpart_fractions_and_adjusted_r2():
    y, x1, x2, response, first, second = _varpart_inputs()
    out, export = _run(VarpartStep(), (y, x1, x2), {})
    assert out.dims == ["fraction", "statistic"]
    rows = out.labels["fraction"]
    assert list(rows) == ["a", "b", "c", "d", "X1", "X2", "union"]
    columns = out.labels["statistic"]
    assert set(export) == {"a", "b", "c", "d", "r2", "adj_r2", "df"}
    assert export["a"] + export["b"] + export["c"] + export["d"] == pytest.approx(1.0)
    assert export["c"] == pytest.approx(export["adj_r2"][0] + export["adj_r2"][1]
                                        - export["adj_r2"][2], abs=1e-12)
    assert np.isnan(out.data[rows["d"], columns["r2"]])
    assert out.data[rows["c"], columns["df"]] == pytest.approx(0.0)
    def rounded(matrix):
        return np.asarray(matrix, dtype=np.float32).astype(np.float64)

    base = rounded(response)
    centered = base - base.mean(axis=0)
    ss = np.sum(centered ** 2)
    n = base.shape[0]

    def adjusted(matrix):
        data = rounded(matrix)
        z = (data - data.mean(axis=0)) / data.std(axis=0, ddof=1)
        coef = np.linalg.lstsq(z, centered, rcond=None)[0]
        r2 = np.sum((z @ coef) ** 2) / ss
        rank = np.linalg.matrix_rank(z)
        return r2, 1.0 - (1.0 - r2) * (n - 1) / (n - rank - 1)

    expected = [adjusted(first), adjusted(second),
                adjusted(np.hstack([first, second]))]
    for index, (r2, adj) in enumerate(expected):
        assert export["r2"][index] == pytest.approx(r2, rel=1e-9)
        assert export["adj_r2"][index] == pytest.approx(adj, rel=1e-9)
    assert out.info["testable"] == {"a": True, "b": True, "c": False, "d": False}


def test_varpart_rejects_constant_predictor():
    y, x1, _, _, first, _ = _varpart_inputs()
    first[:, 1] = 3.0
    x1 = _form(first, ["sample", "predictor"],
               {"sample": y.labels["sample"], "predictor": {"p0": 0, "p1": 1}})
    with pytest.raises(StepError, match="constant column"):
        _run(VarpartStep(), (y, x1, _varpart_inputs()[2]), {})


def test_varpart_rejects_label_mismatch():
    y, x1, x2, _, _, _ = _varpart_inputs()
    labels = {"sample": {"other": 0}, "predictor_b": {"q0": 0, "q1": 1}}
    broken = _form(np.zeros((1, 2)), ["sample", "predictor_b"], labels)
    with pytest.raises(StepError, match="share the same sample labels"):
        _run(VarpartStep(), (y, x1, broken), {})


def test_mrc_reader_fixture():
    form = MrcReader().read(FIXTURE, ["slice", "voxel"],
                            {"slice": "auto", "voxel": "builtin"})
    form.validate()
    assert form.data.shape == (2, 12)
    np.testing.assert_allclose(form.data[0], np.arange(12, dtype=np.float32))
    np.testing.assert_allclose(form.data[1], np.arange(12, 24, dtype=np.float32))
    assert list(form.labels["slice"]) == ["0", "1"]
    assert form.info["format"] == "MRC"
    assert form.info["layout"] == "ccp4"
    assert form.info["byte_order"] == "little"
    assert (form.info["nx"], form.info["ny"], form.info["nz"]) == (4, 3, 2)
    assert form.info["mode"] == 2
    np.testing.assert_allclose(form.info["voxel_size"], [1.5, 2.5, 3.5], atol=1e-6)


def test_mrc_reader_slice_range():
    form = MrcReader().read(FIXTURE, ["slice", "voxel"], {},
                            slice_start=1, slice_stop=2)
    assert form.data.shape == (1, 12)
    assert list(form.labels["slice"]) == ["1"]
    np.testing.assert_allclose(form.data[0], np.arange(12, 24, dtype=np.float32))


def test_mrc_reader_rejects_truncated_file(tmp_path):
    header_only = tmp_path / "short.mrc"
    header_only.write_bytes(FIXTURE.read_bytes()[:1024])
    with pytest.raises(ReaderError, match="file has 1024 bytes"):
        MrcReader().read(header_only, ["slice", "voxel"], {})


def test_mrc_reader_rejects_unknown_mode(tmp_path):
    raw = bytearray(FIXTURE.read_bytes())
    raw[12:16] = (5).to_bytes(4, "little")
    broken = tmp_path / "mode.mrc"
    broken.write_bytes(bytes(raw))
    with pytest.raises(ReaderError, match="not valid"):
        MrcReader().read(broken, ["slice", "voxel"], {})


def test_mrc_reader_matches_mrcfile_oracle():
    mrcfile = pytest.importorskip("mrcfile")
    with mrcfile.open(FIXTURE) as handle:
        expected = handle.data.reshape(2, 12)
        voxel = handle.voxel_size
        header = handle.header
    form = MrcReader().read(FIXTURE, ["slice", "voxel"], {})
    np.testing.assert_allclose(form.data, expected)
    voxel_array = np.array([float(voxel["x"]), float(voxel["y"]),
                            float(voxel["z"])])
    np.testing.assert_allclose(form.info["voxel_size"], voxel_array, rtol=1e-6)
    assert form.info["mode"] == int(header.mode)
    assert (form.info["nx"], form.info["ny"], form.info["nz"]) == (
        int(header.nx), int(header.ny), int(header.nz))


def test_mrc_reader_dispatch():
    from src.reader import pick_reader

    assert isinstance(pick_reader(FIXTURE).implementation(), MrcReader)
