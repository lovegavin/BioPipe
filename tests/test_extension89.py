"""Tests for the 1.4.0 causal-inference operators and the MuData reader."""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader import pick_reader
from src.reader.readers.h5mu_reader import H5muReader
from src.task.step.steps.iptw_effect import IptwEffectStep
from src.task.step.steps.iv_2sls import Iv2slsStep
from src.task.step.steps.rdd import RddStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    return Form(
        data=np.asarray(data, dtype=np.float64),
        dims=list(dims),
        labels=dict(labels),
        info={"missing_code": np.nan},
    )


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[params.get("output", step.name)]


def _table(columns, sample_dim="sample", feature_dim="feature", samples=None):
    names = list(columns)
    data = np.column_stack([columns[name] for name in names])
    if samples is None:
        samples = [f"s{index}" for index in range(data.shape[0])]
    labels = {
        sample_dim: {name: index for index, name in enumerate(samples)},
        feature_dim: {name: index for index, name in enumerate(names)},
    }
    return _form(data, [sample_dim, feature_dim], labels)


def _values(form, dim):
    names = [name for name, _ in sorted(form.labels[dim].items(), key=lambda item: item[1])]
    return names


# ---------------------------------------------------------------------------
# Two-stage least squares


def _iv_data(n=180, seed=5):
    rng = np.random.default_rng(seed)
    z1 = rng.normal(size=n)
    z2 = rng.normal(size=n)
    w = rng.normal(size=n)
    u = rng.normal(size=n)
    x = 0.7 * z1 + 0.3 * z2 + 0.5 * w + 0.6 * u + rng.normal(size=n)
    y = 1.0 + 1.8 * x + 0.5 * w + 1.2 * u
    return {"y": y, "x": x, "w": w, "z1": z1, "z2": z2}


def test_iv_2sls_matches_linearmodels():
    pytest.importorskip("linearmodels")
    from linearmodels.iv import IV2SLS

    data = _iv_data()
    table = _table(data)
    out = _run(
        Iv2slsStep(),
        {"output": "output", "outcome_label": "y", "endog_labels": ["x"],
         "instrument_labels": ["z1"], "exog_labels": ["w"]},
        table,
    )
    terms = _values(out, "term")
    columns = _values(out, "statistic")
    coef = out.data[:, columns.index("coef")]
    se = out.data[:, columns.index("se")]
    n = data["y"].size
    exog = np.column_stack([np.ones(n), data["w"]])
    reference = IV2SLS(data["y"], exog, data["x"], data["z1"]).fit(cov_type="unadjusted")
    assert terms == ["const", "w", "x"]
    np.testing.assert_allclose(coef, reference.params.values, rtol=1e-6, atol=5e-7)
    np.testing.assert_allclose(se, reference.std_errors.values, rtol=1e-6, atol=5e-7)


def test_iv_2sls_overidentified_matches_linearmodels():
    pytest.importorskip("linearmodels")
    from linearmodels.iv import IV2SLS

    data = _iv_data(n=220, seed=8)
    table = _table(data)
    out = _run(
        Iv2slsStep(),
        {"output": "output", "outcome_label": "y", "endog_labels": ["x"],
         "instrument_labels": ["z1", "z2"]},
        table,
    )
    coef = dict(zip(_values(out, "term"), out.data[:, 0]))
    n = data["y"].size
    reference = IV2SLS(data["y"], np.ones((n, 1)), data["x"],
                       np.column_stack([data["z1"], data["z2"]])).fit()
    np.testing.assert_allclose(coef["x"], reference.params.values[-1], rtol=1e-6, atol=5e-7)
    assert out.info["n_instruments"] == 2


def test_iv_2sls_errors():
    data = _iv_data(n=60)
    table = _table(data)
    with pytest.raises(StepError, match="not found"):
        _run(Iv2slsStep(), {"output": "output", "outcome_label": "y",
                            "endog_labels": ["x"], "instrument_labels": ["nope"]}, table)
    with pytest.raises(StepError, match="at least as many instruments"):
        _run(Iv2slsStep(), {"output": "output", "outcome_label": "y",
                            "endog_labels": ["x", "w"], "instrument_labels": ["z1"]}, table)
    with pytest.raises(StepError, match="rank deficient"):
        collinear = dict(data)
        collinear["z2"] = 2.0 * data["z1"]
        _run(Iv2slsStep(), {"output": "output", "outcome_label": "y",
                            "endog_labels": ["x"], "instrument_labels": ["z1", "z2"]},
             _table(collinear))


# ---------------------------------------------------------------------------
# IPTW


def _iptw_data(n=500, seed=13, effect=1.5):
    rng = np.random.default_rng(seed)
    c1 = rng.normal(size=n)
    c2 = rng.normal(size=n)
    propensity = 1.0 / (1.0 + np.exp(-(0.6 * c1 - 0.4 * c2)))
    treatment = (rng.random(n) < propensity).astype(float)
    outcome = 1.0 + effect * treatment + 0.8 * c1 + 0.5 * c2 + rng.normal(0, 0.5, n)
    return {"t": treatment, "y": outcome, "c1": c1, "c2": c2}


def test_iptw_recovers_treatment_effect():
    data = _iptw_data()
    table = _table(data)
    out = _run(
        IptwEffectStep(),
        {"output": "output", "treatment_label": "t", "outcome_label": "y",
         "covariate_labels": ["c1", "c2"]},
        table,
    )
    rows = dict(zip(_values(out, "statistic"), out.data[:, 0]))
    assert abs(rows["effect"] - 1.5) < 0.15
    assert rows["se"] > 0.0
    assert rows["n_treated"] + rows["n_control"] == 500
    assert 0.0 < rows["ps_min"] <= rows["ps_max"] < 1.0
    assert out.info["estimand"] == "ate"


def test_iptw_att_and_errors():
    data = _iptw_data(seed=21)
    table = _table(data)
    out = _run(
        IptwEffectStep(),
        {"output": "output", "treatment_label": "t", "outcome_label": "y",
         "covariate_labels": ["c1"], "estimand": "att"},
        table,
    )
    assert out.info["estimand"] == "att"
    bad = dict(data)
    bad["t"] = np.full_like(data["t"], 2.0)
    with pytest.raises(StepError, match="0/1"):
        _run(IptwEffectStep(), {"output": "output", "treatment_label": "t",
                                "outcome_label": "y"}, _table(bad))
    single = dict(data)
    single["t"] = np.zeros_like(data["t"])
    with pytest.raises(StepError, match="two treated"):
        _run(IptwEffectStep(), {"output": "output", "treatment_label": "t",
                                "outcome_label": "y"}, _table(single))
    with pytest.raises(StepError, match="trim"):
        _run(IptwEffectStep(), {"output": "output", "treatment_label": "t",
                                "outcome_label": "y", "trim": 0.7}, table)


# ---------------------------------------------------------------------------
# Regression discontinuity


def _rdd_data(n=300, seed=17, jump=1.2):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-1.0, 1.0, n)
    y = 0.4 + 0.5 * x + jump * (x >= 0.0)
    return {"x": x, "y": y}


def test_rdd_recovers_linear_jump():
    data = _rdd_data()
    out = _run(
        RddStep(),
        {"output": "output", "running_label": "x", "outcome_label": "y", "bandwidth": 0.5},
        _table(data),
    )
    rows = dict(zip(_values(out, "statistic"), out.data[:, 0]))
    assert abs(rows["tau"] - 1.2) < 1e-6
    assert rows["se"] >= 0.0
    assert rows["n_left"] + rows["n_right"] == out.info["n_obs_used"]


def test_rdd_uniform_kernel_and_errors():
    data = _rdd_data(seed=19, jump=0.8)
    out = _run(
        RddStep(),
        {"output": "output", "running_label": "x", "outcome_label": "y",
         "bandwidth": 0.6, "kernel": "uniform"},
        _table(data),
    )
    tau = dict(zip(_values(out, "statistic"), out.data[:, 0]))["tau"]
    assert abs(tau - 0.8) < 1e-6
    with pytest.raises(StepError, match="too few observations"):
        _run(RddStep(), {"output": "output", "running_label": "x",
                         "outcome_label": "y", "bandwidth": 0.001}, _table(data))
    with pytest.raises(StepError, match="unknown kernel"):
        _run(RddStep(), {"output": "output", "running_label": "x",
                         "outcome_label": "y", "bandwidth": 0.5, "kernel": "quartic"},
             _table(data))


# ---------------------------------------------------------------------------
# MuData reader


def _make_h5mu(path: Path):
    anndata = pytest.importorskip("anndata")
    mudata = pytest.importorskip("mudata")
    import pandas as pd
    import scipy.sparse as sp

    rng = np.random.default_rng(23)
    n = 40
    dense = rng.normal(size=(n, 4))
    counts = np.abs(rng.normal(size=(n, 4)))
    first = anndata.AnnData(
        X=dense,
        obs={"batch": [f"b{index % 3}" for index in range(n)]},
        var=pd.DataFrame({"kind": [f"g{index}" for index in range(4)]},
                         index=[f"g{index}" for index in range(4)]),
        layers={"counts": counts},
    )
    sparse = sp.csr_matrix(np.abs(rng.normal(size=(n, 3))))
    second = anndata.AnnData(
        X=sparse,
        obs={"batch": [f"b{index % 3}" for index in range(n)]},
        var=pd.DataFrame({"kind": [f"p{index}" for index in range(3)]},
                         index=[f"p{index}" for index in range(3)]),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mudata.MuData({"rna": first, "prot": second}).write(str(path))
    return dense, counts, sparse.toarray()


def test_h5mu_reader_reads_dense_and_sparse(tmp_path):
    dense, counts, sparse = _make_h5mu(tmp_path / "demo.h5mu")
    reader = H5muReader()
    dense_form = reader.read(tmp_path / "demo.h5mu", ["sample", "feature"], {}, modality="rna")
    np.testing.assert_allclose(dense_form.data, dense.astype(np.float32), rtol=1e-6, atol=1e-6)
    assert dense_form.info["format"] == "dense"
    assert dense_form.info["n_modalities"] == 2
    assert set(dense_form.labels["sample"]) == {str(index) for index in range(dense.shape[0])}
    assert dense_form.labels["feature"] == {f"g{index}": index for index in range(4)}
    layer_form = reader.read(tmp_path / "demo.h5mu", ["sample", "feature"], {},
                             modality="rna", layer="counts")
    np.testing.assert_allclose(layer_form.data, counts.astype(np.float32), rtol=1e-6, atol=1e-6)
    sparse_form = reader.read(tmp_path / "demo.h5mu", ["sample", "feature"], {}, modality="prot")
    np.testing.assert_allclose(sparse_form.data, sparse.astype(np.float32), rtol=1e-6, atol=1e-6)
    assert sparse_form.info["format"] == "sparse"


def test_h5mu_reader_dispatch_and_errors(tmp_path):
    path = tmp_path / "demo.h5mu"
    _make_h5mu(path)
    assert isinstance(pick_reader(path).implementation(), H5muReader)
    reader = H5muReader()
    with pytest.raises(Exception, match="exactly two dims"):
        reader.read(path, ["sample"], {}, modality="rna")
    with pytest.raises(Exception, match="not found"):
        reader.read(path, ["sample", "feature"], {}, modality="missing")
    with pytest.raises(Exception, match="pass modality"):
        reader.read(path, ["sample", "feature"], {})
    plain = tmp_path / "plain.h5mu"
    import h5py
    with h5py.File(plain, "w") as handle:
        handle.create_dataset("other", data=np.zeros(3))
    with pytest.raises(Exception, match="no /mod"):
        reader.read(plain, ["sample", "feature"], {}, modality="rna")
