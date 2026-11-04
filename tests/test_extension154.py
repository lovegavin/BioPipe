"""Tests for the interface distance histogram operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.interface_distance_histogram import InterfaceDistanceHistogramStep


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element="C", record="ATOM"):
    return (
        f"{record:<6}{serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{10.0:>6.2f}          {element:>2}"
    )


def _pdb(rows: list[str]) -> Form:
    from src.reader import read_source
    import tempfile
    from pathlib import Path

    directory = Path(tempfile.mkdtemp())
    path = directory / "hist.pdb"
    path.write_text("HEADER    HIST\n" + "\n".join(rows) + "\nEND\n", encoding="utf-8")
    return read_source(path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[ctx.step_params["output"]], step.export(ctx)


FIXTURE = [
    _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
    _atom(2, "CA", "GLY", "A", 2, 3.0, 0.0, 0.0),
    _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 4.0),
    _atom(4, "CA", "SER", "B", 2, 2.0, 0.0, 0.0),
]


def test_histogram_bins_hand_computed():
    form = _pdb(FIXTURE)
    out, export = _run(
        InterfaceDistanceHistogramStep(),
        {"binder_chains": "A", "target_chains": "B", "cutoff": 6.0, "bin_width": 0.5},
        [form],
    )
    assert list(out.dims) == ["distance_bin", "statistic"]
    data = out.data
    assert data.shape == (12, 5)
    # Distances: 1.0 (A2-B2), 2.0 (A1-B2), 4.0 (A1-B1), 5.0 (A2-B1).
    bins = {label: data[index, 3] for label, index in out.labels["distance_bin"].items()}
    assert bins["1.00-1.50"] == 1.0
    assert bins["2.00-2.50"] == 1.0
    assert bins["4.00-4.50"] == 1.0
    assert bins["5.00-5.50"] == 1.0
    assert float(data[:, 3].sum()) == 4.0
    assert out.info["n_atom_pairs"] == 4
    assert out.info["min_distance"] == 1.0
    assert out.info["median_distance"] == 3.0
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["B"]
    assert export["n_atom_pairs"] == 4


def test_histogram_ignores_pairs_beyond_cutoff():
    form = _pdb(FIXTURE)
    out, _ = _run(
        InterfaceDistanceHistogramStep(),
        {"binder_chains": "A", "target_chains": "B", "cutoff": 2.5, "bin_width": 0.5},
        [form],
    )
    assert out.info["n_atom_pairs"] == 2
    assert out.info["max_distance"] == 2.0
    assert out.data.shape == (5, 5)


def test_histogram_matches_brute_force():
    form = _pdb(FIXTURE)
    out, _ = _run(
        InterfaceDistanceHistogramStep(),
        {"binder_chains": "A", "target_chains": "B", "cutoff": 6.0, "bin_width": 0.25},
        [form],
    )
    coords = np.asarray(form.data[:, :3], dtype=np.float64)
    chain = form.info["encoders"]["field"]["chain"].inverse_transform(form.data[:, 6])
    distances = [
        float(np.linalg.norm(coords[i] - coords[j]))
        for i in range(len(coords))
        if chain[i] == "A"
        for j in range(len(coords))
        if chain[j] == "B" and 0 < np.linalg.norm(coords[i] - coords[j]) <= 6.0
    ]
    edges = np.arange(0.0, 6.0 + 0.25, 0.25)
    counts, _ = np.histogram(distances, bins=edges)
    assert np.array_equal(out.data[:, 3].astype(np.int64), counts)
    assert out.info["n_atom_pairs"] == len(distances)


def test_histogram_derives_target_chains():
    form = _pdb(FIXTURE)
    out, _ = _run(
        InterfaceDistanceHistogramStep(),
        {"binder_chains": "B", "target_chains": "", "cutoff": 6.0, "bin_width": 0.5},
        [form],
    )
    assert out.info["target_chains"] == ["A"]


def test_histogram_parameter_errors():
    form = _pdb(FIXTURE)
    with pytest.raises(StepError, match="cutoff must be positive"):
        _run(InterfaceDistanceHistogramStep(), {"cutoff": 0.0}, [form])
    with pytest.raises(StepError, match="bin_width must be positive"):
        _run(InterfaceDistanceHistogramStep(), {"bin_width": -1.0}, [form])
    with pytest.raises(StepError, match="bin_width must not exceed cutoff"):
        _run(InterfaceDistanceHistogramStep(), {"cutoff": 2.0, "bin_width": 4.0}, [form])
    with pytest.raises(StepError, match="not found in the PDB form"):
        _run(InterfaceDistanceHistogramStep(), {"binder_chains": "Z"}, [form])


def test_histogram_rejects_wrong_dims():
    form = _pdb(FIXTURE)
    wrong = Form(
        data=form.data,
        dims=["atom", "field", "extra"],
        labels={
            "atom": form.labels["atom"],
            "field": form.labels["field"],
            "extra": {"0": 0},
        },
        info={"missing_code": np.nan},
    )
    wrong.data = np.concatenate([form.data, np.zeros((len(form.data), 1), np.float32)], axis=1)
    with pytest.raises(StepError, match="PDB form with dims"):
        _run(InterfaceDistanceHistogramStep(), {}, [wrong])


def test_histogram_empty_interface_raises():
    rows = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "SER", "B", 1, 40.0, 0.0, 0.0),
    ]
    form = _pdb(rows)
    with pytest.raises(StepError, match="no binder-target atom pair"):
        _run(InterfaceDistanceHistogramStep(), {"cutoff": 5.0}, [form])
