"""Tests for 1.8.0 operators and reader: pcnm, fisher_alpha, cuzick, TpedReader."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.tped_reader import TpedReader
from src.task.step.steps.cuzick import CuzickTestStep
from src.task.step.steps.fisher_alpha import FisherAlphaStep
from src.task.step.steps.pcnm import PcnmStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _labels(names):
    return {name: index for index, name in enumerate(names)}


GRID = np.array(
    [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]
)
GRID_NAMES = [f"s{index}" for index in range(6)]
GRID_DISTANCE = np.sqrt(((GRID[:, None, :] - GRID[None, :, :]) ** 2).sum(axis=2))
R_VECTORS = np.array(
    [
        [-0.5, 0.353553390593, 0.288675134595, 0.5],
        [0.0, 0.5, -0.577350269190, 0.0],
        [0.5, 0.353553390593, 0.288675134595, -0.5],
        [-0.5, -0.353553390593, 0.288675134595, -0.5],
        [0.0, -0.5, -0.577350269190, 0.0],
        [0.5, -0.353553390593, 0.288675134595, 0.5],
    ]
)


def _distance_form(matrix, names):
    return _form(matrix, ["sample", "sample_b"], {"sample": _labels(names), "sample_b": _labels(names)})


def test_pcnm_matches_vegan_axes():
    distance_form = _distance_form(GRID_DISTANCE, GRID_NAMES)
    result, exported = _run(PcnmStep(), {}, (distance_form,))
    assert result.dims == ["sample", "axis"]
    assert result.data.shape == (6, 4)
    np.testing.assert_allclose(result.info["eigenvalues"], [15.5, 11.1066017178, 5.5, 0.5], atol=1e-8)
    assert result.info["threshold"] == pytest.approx(1.0)
    assert exported["n_axes"] == 4
    np.testing.assert_allclose(np.abs(result.data), np.abs(R_VECTORS), atol=1e-6)
    norms = np.linalg.norm(result.data, axis=0)
    np.testing.assert_allclose(norms, np.ones(4), atol=1e-6)
    pivot = np.argmax(np.abs(result.data), axis=0)
    for column in range(4):
        vector = result.data[:, column]
        strong = int(np.flatnonzero(np.abs(vector) >= float(np.max(np.abs(vector))) * (1.0 - 1e-9))[0])
        assert vector[strong] > 0.0
    assert pivot.shape == (4,)


def test_pcnm_threshold_and_axis_limit():
    distance_form = _distance_form(GRID_DISTANCE, GRID_NAMES)
    result, exported = _run(PcnmStep(), {"threshold": 2.0, "n_axes": 2}, (distance_form,))
    assert result.data.shape == (6, 2)
    assert result.info["threshold"] == pytest.approx(2.0)
    assert exported["n_axes"] == 2
    np.testing.assert_allclose(np.linalg.norm(result.data, axis=0), np.ones(2), atol=1e-6)


def test_pcnm_rejects_bad_distance_matrices():
    tiny = _distance_form(GRID_DISTANCE[:2, :2], GRID_NAMES[:2])
    with pytest.raises(Exception, match="at least three samples"):
        _run(PcnmStep(), {}, (tiny,))
    asymmetric = GRID_DISTANCE.copy()
    asymmetric[0, 1] += 1.0
    asymmetric[1, 0] -= 1.0
    with pytest.raises(Exception, match="symmetric"):
        _run(PcnmStep(), {}, (_distance_form(asymmetric, GRID_NAMES),))
    with pytest.raises(Exception, match="positive finite"):
        _run(PcnmStep(), {"threshold": 0.0}, (_distance_form(GRID_DISTANCE, GRID_NAMES),))


COMMUNITY = np.array(
    [
        [10.0, 1.0, 0.0, 2.0],
        [0.0, 5.0, 5.0, 0.0],
        [1.0, 1.0, 1.0, 1.0],
        [3.0, 0.0, 0.0, 0.0],
    ]
)


def _community_form():
    samples = [f"s{index}" for index in range(4)]
    taxa = ["t1", "t2", "t3", "t4"]
    return _form(COMMUNITY, ["sample", "taxon"], {"sample": _labels(samples), "taxon": _labels(taxa)})


def test_fisher_alpha_matches_solution_and_vegan_values():
    result, exported = _run(FisherAlphaStep(), {}, (_community_form(),))
    assert result.dims == ["sample", "statistic"]
    assert list(result.labels["statistic"]) == ["alpha"]
    values = result.data[:, 0]
    np.testing.assert_allclose(values[:2], [1.22254799454805, 0.7517669176875106], atol=1e-6)
    assert values[3] == pytest.approx(0.525261477587570, abs=2e-4)
    assert np.isinf(values[2])  # all singletons
    for row, alpha in zip(COMMUNITY[:2], values[:2]):
        species = float(np.count_nonzero(row))
        individuals = float(row.sum())
        residual = alpha * np.log1p(individuals / alpha) - species
        assert abs(residual) < 1e-6
    assert exported["n_samples"] == 4


def test_cuzick_trend_matches_pmcmrplus():
    samples = [f"s{index}" for index in range(15)]
    data = _form(
        np.arange(1.0, 16.0).reshape(1, 15),
        ["feature", "sample"],
        {"feature": {"x": 0}, "sample": _labels(samples)},
    )
    groups = np.repeat([1.0, 2.0, 3.0], 5).reshape(15, 1)
    meta = _form(groups, ["sample", "feature"], {"sample": _labels(samples), "feature": {"group": 0}})
    result, exported = _run(CuzickTestStep(), {"group_label": "group"}, (data, meta))
    assert result.dims == ["feature", "statistic"]
    row = result.data[0]
    assert row[0] == pytest.approx(290.0, rel=1e-6)  # T
    assert row[1] == pytest.approx(3.53553390593274, rel=1e-6)  # z
    assert row[2] == pytest.approx(0.000406952017444959, rel=1e-5)
    assert row[3] == pytest.approx(15.0)
    assert exported["n_groups"] == 3
    assert result.info["scores"] == [1.0, 2.0, 3.0]


def test_cuzick_scores_and_errors():
    samples = [f"s{index}" for index in range(15)]
    data = _form(
        np.arange(1.0, 16.0).reshape(1, 15),
        ["feature", "sample"],
        {"feature": {"x": 0}, "sample": _labels(samples)},
    )
    groups = np.repeat([1.0, 2.0, 3.0], 5).reshape(15, 1)
    meta = _form(groups, ["sample", "feature"], {"sample": _labels(samples), "feature": {"group": 0}})
    result, _ = _run(
        CuzickTestStep(), {"group_label": "group", "scores": [3.0, 1.0, 2.0]}, (data, meta)
    )
    assert result.data[0, 1] == pytest.approx(-1.76776695296637, rel=1e-6)
    with pytest.raises(Exception, match="scores has 2 values"):
        _run(CuzickTestStep(), {"group_label": "group", "scores": [1.0, 2.0]}, (data, meta))
    flat = _form(
        np.ones((1, 15)), ["feature", "sample"], {"feature": {"x": 0}, "sample": _labels(samples)}
    )
    with pytest.raises(Exception, match="variance is zero"):
        _run(CuzickTestStep(), {"group_label": "group"}, (flat, meta))


def _write_tped(directory: Path, tped_lines, samples):
    path = directory / "geno.tped"
    path.write_text("\n".join(tped_lines) + "\n", encoding="utf-8")
    tfam = [f"F1 {sample} 0 0 1 -9" for sample in samples]
    (directory / "geno.tfam").write_text("\n".join(tfam) + "\n", encoding="utf-8")
    return path


TPED_LINES = [
    "1 rs1 0 100 1 1 2 2 0 0",
    "1 rs2 0 200 1 2 2 1 1 1",
    "2 rs3 0 300 2 2 2 2 1 2",
]
TPED_SAMPLES = ["S1", "S2", "S3"]


def test_tped_reader_parses_codes_and_metadata(tmp_path):
    path = _write_tped(tmp_path, TPED_LINES, TPED_SAMPLES)
    assert isinstance(pick_reader(path).implementation(), TpedReader)
    form = TpedReader().read(path, ["variant", "sample"], {})
    form.validate()
    assert form.dims == ["variant", "sample"]
    assert form.data.shape == (3, 3)
    np.testing.assert_allclose(
        form.data[0, :2], [2.0, 0.0]
    )
    assert np.isnan(form.data[0, 2])
    np.testing.assert_allclose(form.data[1], [1.0, 1.0, 2.0])
    np.testing.assert_allclose(form.data[2], [0.0, 0.0, 1.0])
    assert form.info["chrom"] == ["1", "1", "2"]
    assert form.info["pos"] == [100, 200, 300]
    assert form.info["representation"] == "hard_call"
    assert form.info["ploidy"] == 2
    assert set(form.labels["variant"]) == {"rs1", "rs2", "rs3"}
    assert set(form.labels["sample"]) == set(TPED_SAMPLES)


def test_tped_reader_rejects_invalid_files(tmp_path):
    path = _write_tped(tmp_path, TPED_LINES, TPED_SAMPLES)
    path.with_suffix(".tfam").unlink()
    with pytest.raises(Exception, match="sibling"):
        TpedReader().read(path, ["variant", "sample"], {})
    _write_tped(tmp_path, ["1 rs1 0 100 1 3 2 2 0 0"], TPED_SAMPLES)
    with pytest.raises(Exception, match="invalid allele code"):
        TpedReader().read(path, ["variant", "sample"], {})
    _write_tped(tmp_path, ["1 rs1 0 100 1 1 2 2"], TPED_SAMPLES)
    with pytest.raises(Exception, match="columns"):
        TpedReader().read(path, ["variant", "sample"], {})
    (tmp_path / "geno.tped").write_text("", encoding="utf-8")
    with pytest.raises(Exception, match="no variants"):
        TpedReader().read(path, ["variant", "sample"], {})


def test_tped_reader_roundtrips_through_plink(tmp_path):
    plink = shutil.which("plink")
    if plink is None:
        pytest.skip("plink is not available")
    path = _write_tped(tmp_path, TPED_LINES, TPED_SAMPLES)
    prefix = tmp_path / "geno"
    completed = subprocess.run(
        [plink, "--tfile", str(prefix), "--make-bed", "--out", str(prefix)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    from src.reader import pick_reader as select

    bed_form = select(prefix.with_suffix(".bed")).read(prefix.with_suffix(".bed"), ["variant", "sample"], {})
    assert bed_form.data.shape == (3, 3)
    tped_form = TpedReader().read(path, ["variant", "sample"], {})
    np.testing.assert_array_equal(np.isnan(bed_form.data), np.isnan(tped_form.data))
    np.testing.assert_array_equal(bed_form.data == 1.0, tped_form.data == 1.0)
