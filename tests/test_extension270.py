from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context import Context
from src.task.runner import run


def _ctx(task_dir: Path, out_name: str, params: dict) -> Context:
    ctx = Context(str(task_dir / "task"), {"params": {}})
    ctx.step_params = {"output": out_name, **params}
    return ctx

from src.task.step.steps.esm_embedding_ridge_probe import (
    parse_targets,
    probe_rows,
    resolve_targets,
    ridge_predict,
    validate_input,
)


def _form(data, targets=None) -> Form:
    data = np.asarray(data, dtype=np.float32)
    info = {"missing_code": np.nan}
    if targets is not None:
        info["targets"] = list(targets)
    return Form(
        data=data,
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"seq{i + 1}": i for i in range(data.shape[0])},
            "embedding": {f"e{i}": i for i in range(data.shape[1])},
        },
        info=info,
    )


def test_parse_and_resolve_targets():
    assert parse_targets("1, 2;3 4.5").tolist() == [1.0, 2.0, 3.0, 4.5]
    with pytest.raises(StepError, match="is not a number"):
        parse_targets("1, x")
    with pytest.raises(StepError, match="targets is required"):
        parse_targets("")
    form = _form(np.zeros((2, 1)), targets=[1.5, 2.5])
    assert resolve_targets(form, "sequence", "").tolist() == [1.5, 2.5]
    with pytest.raises(StepError, match="targets are required"):
        resolve_targets(_form(np.zeros((2, 1))), "sequence", "")


def test_validate_input_errors():
    data = np.zeros((3, 2))
    wrong = Form(
        data=data,
        dims=["sample", "feature"],
        labels={"sample": {"a": 0, "b": 1, "c": 2}, "feature": {"x": 0, "y": 1}},
        info={},
    )
    with pytest.raises(StepError, match="expected a"):
        validate_input(wrong, "sequence", "embedding", np.zeros(3))
    with pytest.raises(StepError, match="got 2 targets for 3 samples"):
        validate_input(_form(data), "sequence", "embedding", np.zeros(2))
    bad = data.copy()
    bad[0, 0] = np.nan
    with pytest.raises(StepError, match="non-finite"):
        validate_input(_form(bad), "sequence", "embedding", np.zeros(3))


def test_ridge_recovers_an_exact_linear_map():
    x = np.asarray([[0.0], [1.0], [2.0], [3.0], [4.0], [5.0], [6.0], [7.0]])
    y = 2.0 * x[:, 0] + 1.0
    rows, summary = probe_rows(x, y, folds=4, alpha=1e-9)
    assert summary["mean_r2"] == pytest.approx(1.0, abs=1e-6)
    assert summary["mean_rmse"] == pytest.approx(0.0, abs=1e-6)


def test_multi_feature_map_beats_the_baseline():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(12, 3))
    y = 3.0 * x[:, 0] - 2.0 * x[:, 1] + 0.5 * x[:, 2]
    rows, summary = probe_rows(x, y, folds=3, alpha=1e-9)
    assert summary["mean_r2"] > 0.999
    assert summary["baseline_rmse"] > 0.1
    assert summary["mean_rmse"] < summary["baseline_rmse"]


def test_matches_sklearn_ridge_when_available():
    pytest.importorskip("sklearn")
    from sklearn.linear_model import Ridge

    rng = np.random.default_rng(11)
    x = rng.normal(size=(20, 2))
    y = x[:, 0] - 3.0 * x[:, 1] + 2.0
    train, test = slice(0, 15), slice(15, 20)
    ours = ridge_predict(x[train], y[train], x[test], alpha=0.5)
    mean = x[train].mean(axis=0)
    scale = x[train].std(axis=0)
    model = Ridge(alpha=0.5).fit((x[train] - mean) / scale, y[train])
    theirs = model.predict((x[test] - mean) / scale)
    assert np.allclose(ours, theirs, atol=1e-8)


def test_constant_targets_give_nan_r2():
    x = np.arange(8, dtype=float).reshape(-1, 1)
    rows, summary = probe_rows(x, np.ones(8), folds=4, alpha=1.0)
    assert all(np.isnan(row["r2"]) for row in rows)
    assert np.isnan(summary["mean_r2"])


def test_run_reports_folds_and_summary(tmp_path):
    rng = np.random.default_rng(5)
    x = rng.normal(size=(10, 3))
    y = 2.0 * x[:, 0] + 0.5
    form = _form(x, targets=y)
    params = {"cv_folds": 5, "alpha": 1e-6}
    ctx = _ctx(tmp_path, "probe", params)
    ctx["emb"] = form
    run(ctx, [{"name": "esm_embedding_ridge_probe", "inputs": ["emb"], "params": params}])
    result = ctx["probe"]
    assert result.dims == ["metric", "statistic"]
    assert result.data.shape[0] == 9
    labels = list(result.labels["metric"])
    assert labels[:5] == ["fold1", "fold2", "fold3", "fold4", "fold5"]
    assert labels[-4:] == ["mean_r2", "std_r2", "mean_rmse", "baseline_rmse"]
    assert result.info["mean_r2"] > 0.99


def test_run_errors(tmp_path):
    rng = np.random.default_rng(9)
    x = rng.normal(size=(6, 2))
    form = _form(x, targets=np.arange(6, dtype=float))
    params = {"targets": "0,1,2"}
    ctx = _ctx(tmp_path, "probe", params)
    ctx["emb"] = form
    with pytest.raises(StepError, match="got 3 targets for 6 samples"):
        run(ctx, [{"name": "esm_embedding_ridge_probe", "inputs": ["emb"], "params": params}])
    params = {}
    ctx = _ctx(tmp_path, "probe", params)
    ctx["emb"] = _form(x)
    with pytest.raises(StepError, match="targets are required"):
        run(ctx, [{"name": "esm_embedding_ridge_probe", "inputs": ["emb"], "params": params}])
    params = {"targets": "0,1,2,3,4,5", "cv_folds": 1}
    ctx = _ctx(tmp_path, "probe", params)
    ctx["emb"] = form
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "esm_embedding_ridge_probe", "inputs": ["emb"], "params": params}])
