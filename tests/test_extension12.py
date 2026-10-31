from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.reader.readers.mgf_reader import MgfReader
from src.task.step.steps.bland_altman import BlandAltmanStep
from src.task.step.steps.cochran_armitage import CochranArmitageStep
from src.task.step.steps.cumulative_incidence import CumulativeIncidenceStep
from src.task.step.steps.mantel_haenszel import MantelHaenszelStep
from src.task.step.steps.remove_batch_effect import RemoveBatchEffectStep
from src.task.step.steps.tmm_normalize import TmmNormalizeStep
from src.task.step.steps.tost_equivalence import TostEquivalenceStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def test_tmm_normalization_scales_to_target_and_exports_factors():
    counts = np.array([
        [100, 200, 300],
        [200, 400, 600],
        [300, 100, 200],
        [50, 60, 70],
    ], dtype=np.float32)
    form = _form(counts, ["feature", "sample"],
                 {"feature": _labels([f"g{i}" for i in range(4)]),
                  "sample": _labels([f"s{i}" for i in range(3)])})
    out, info = _run(TmmNormalizeStep(), {}, [form])
    assert out.dims == ["feature", "sample"]
    assert out.data.shape == counts.shape
    factors = np.array([info["norm_factors"][s] for s in ["s0", "s1", "s2"]])
    assert np.allclose(out.data.sum(axis=0) * factors, 1e6, rtol=1e-5)
    assert np.isclose(np.exp(np.mean(np.log(list(info["norm_factors"].values())))), 1.0)
    assert info["reference_sample"] in {"s0", "s1", "s2"}
    assert set(info["effective_library_sizes"]) == {"s0", "s1", "s2"}


def test_remove_batch_effect_aligns_batch_means():
    # feature x sample; batches A and B have a +10 offset.
    data = np.array([
        [1, 2, 3, 11, 12, 13],
        [2, 4, 6, 12, 14, 16],
        [5, 5, 5, 15, 15, 15],
    ], dtype=np.float32)
    expr = _form(data, ["feature", "sample"],
                 {"feature": _labels(["f0", "f1", "f2"]),
                  "sample": _labels([f"s{i}" for i in range(6)])})
    meta = _form(np.array([[0], [0], [0], [1], [1], [1]], dtype=np.float32),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]),
                  "feature": {"batch": 0}})
    out, info = _run(RemoveBatchEffectStep(), {"batch_label": "batch"}, [expr, meta])
    assert out.data.shape == data.shape
    # limma removes sum-to-zero batch effects, centering each feature on
    # its grand mean.
    grand = data.mean(axis=1, keepdims=True)
    batch_means = np.concatenate([
        np.repeat(data[:, :3].mean(axis=1, keepdims=True), 3, axis=1),
        np.repeat(data[:, 3:].mean(axis=1, keepdims=True), 3, axis=1),
    ], axis=1)
    assert np.allclose(out.data, data - (batch_means - grand), atol=1e-5)
    assert info["batches"] == ["0", "1"]
    assert info["batch_sizes"] == {"0": 3, "1": 3}


def test_mantel_haenszel_single_stratum_hand_values():
    # a=10, b=20, c=30, d=40; OR=2/3, expected a=12, var=560/110?
    table = np.array([[10, 20, 30, 40]], dtype=np.float32)
    form = _form(table, ["stratum", "feature"],
                 {"stratum": {"one": 0},
                  "feature": _labels(["case_exposed", "case_unexposed",
                                      "control_exposed", "control_unexposed"])})
    out, info = _run(MantelHaenszelStep(), {}, [form])
    assert out.data.shape == (7, 1)
    assert info["odds_ratio"] == pytest.approx(2 / 3, rel=1e-5)
    assert info["mh_statistic"] == pytest.approx(4 / 5.0909090909, rel=1e-5)
    assert info["p"] == pytest.approx(0.375, abs=2e-3)
    assert info["n_strata"] == 1 and info["n_total"] == 100


def test_cochran_armitage_hand_trend():
    table = np.array([[10, 100], [20, 100], [30, 100]], dtype=np.float32)
    form = _form(table, ["group", "feature"],
                 {"group": _labels(["g0", "g1", "g2"]),
                  "feature": {"cases": 0, "total": 1}})
    out, info = _run(CochranArmitageStep(), {}, [form])
    assert out.data.shape == (6, 1)
    assert info["statistic"] == pytest.approx(12.5, rel=1e-5)
    assert info["p"] == pytest.approx(0.0004069, rel=1e-3)
    assert info["z"] == pytest.approx(np.sqrt(12.5), rel=1e-5)
    assert info["slope"] == pytest.approx(0.1, rel=1e-5)


def test_tost_equivalence_and_bland_altman():
    # group 0 has a mean 1 unit above group 1, margin 2 -> equivalent.
    expr = _form(np.array([[10, 11], [10.5, 11.5], [11, 12], [11.5, 12.5],
                           [9, 10], [9.5, 10.5], [10, 11], [10.5, 11.5]], dtype=np.float32).T,
                 ["feature", "sample"],
                 {"feature": _labels(["f0", "f1"]),
                  "sample": _labels([f"s{i}" for i in range(8)])})
    meta = _form(np.array([[0], [0], [0], [0], [1], [1], [1], [1]], dtype=np.float32),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(8)]),
                  "feature": {"group": 0}})
    out, info = _run(TostEquivalenceStep(), {
        "group_label": "group", "group_a": "0", "group_b": "1", "margin": 2.0,
    }, [expr, meta])
    assert out.data.shape == (2, 14)
    assert out.labels["statistic"]["p"] == 7
    assert np.all(out.data[:, out.labels["statistic"]["equivalent"]] == 1)
    assert np.all(out.data[:, out.labels["statistic"]["p"]] < 0.05)

    ba = _form(np.array([[1, 2], [2, 2], [3, 4], [4, 4]], dtype=np.float32),
               ["sample", "feature"],
               {"sample": _labels([f"s{i}" for i in range(4)]),
                "feature": {"a": 0, "b": 1}})
    out, info = _run(BlandAltmanStep(), {"method_a": "a", "method_b": "b"}, [ba])
    assert info["n"] == 4
    assert info["mean_diff"] == pytest.approx(-0.5)
    assert info["sd_diff"] == pytest.approx(np.std([-1, 0, -1, 0], ddof=1))
    assert info["loa_low"] == pytest.approx(info["mean_diff"] - 1.96 * info["sd_diff"])
    assert out.data.shape == (9, 1)


def test_cumulative_incidence_competing_risk_hand_values():
    clinical = _form(np.array([
        [1, 1], [2, 2], [3, 0], [4, 1], [5, 0], [6, 2],
    ], dtype=np.float32), ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(6)]),
         "feature": {"time": 0, "event": 1}})
    out, info = _run(CumulativeIncidenceStep(), {
        "time_label": "time", "event_label": "event",
    }, [clinical])
    assert out.dims == ["time", "group"]
    assert out.labels["group"] == {"all": 0}
    assert info["n_samples"] == 6
    # At t=1: one event of interest among six -> 1/6.
    assert out.labels["time"]["1"] == 1
    assert out.data[out.labels["time"]["1"], 0] == pytest.approx(1 / 6)
    # At t=4: prior survival 2/3, one event among three at risk.
    assert out.data[out.labels["time"]["4"], 0] == pytest.approx(1 / 6 + (2 / 3) * (1 / 3))


def test_mgf_empty_peak_spectrum_keeps_precursor(tmp_path: Path):
    path = tmp_path / "empty.mgf"
    path.write_text(
        "BEGIN IONS\nTITLE=empty\nPEPMASS=123.4\nCHARGE=2+\nEND IONS\n",
        encoding="utf-8",
    )
    form = MgfReader().read(
        path, ["spectrum", "feature"], {"spectrum": "auto", "feature": "builtin"}
    )
    form.validate()
    assert form.data.shape == (1, 6)
    assert form.data[0, int(form.labels["feature"]["n_peaks"])] == 0
    assert form.data[0, int(form.labels["feature"]["precursor_mz"])] == pytest.approx(123.4)
    assert MgfReader.handles_compression is False
