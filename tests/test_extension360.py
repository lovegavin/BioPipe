import json

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.steps.cox_stuart import CoxStuartStep
from src.task.step.steps.dca import DcaStep
from src.task.step.steps.mantel import MantelStep
from src.task.step.steps.nestedness import NestednessStep
from src.task.step.steps.var_model import VarModelStep


def _form(data, dims, labels, info=None):
    form = Form(data=np.asarray(data, dtype=float), dims=list(dims),
                labels={k: dict(v) for k, v in labels.items()},
                info=dict(info or {"missing_code": np.nan}))
    form.validate()
    return form


def _table(columns):
    data = np.column_stack([np.asarray(v, dtype=float) for v in columns.values()])
    samples = [f"s{i}" for i in range(data.shape[0])]
    features = list(columns)
    form = _form(data, ["sample", "feature"],
                 {"sample": {n: i for i, n in enumerate(samples)},
                  "feature": {n: i for i, n in enumerate(features)}})
    return form


def _ctx(tmp_path, params):
    ctx = Context(tmp_path / "task", {"params": dict(params)})
    ctx.step_params = dict(params)
    return ctx


def test_cox_stuart_export_is_json_serializable(tmp_path):
    form = _table({"value": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]})
    ctx = _ctx(tmp_path, {"value_label": "value", "output": "out"})
    step = CoxStuartStep()
    step.run(ctx, [form])
    json.dumps(step.export(ctx))


def test_dca_metric_dimension_has_one_label_per_column(tmp_path):
    n = 20
    form = _table({"outcome": [0, 1] * (n // 2),
                   "prob": np.linspace(0.05, 0.95, n)})
    ctx = _ctx(tmp_path, {"outcome_label": "outcome",
                          "probability_label": "prob",
                          "thresholds": [0.2, 0.5, 0.8], "output": "out"})
    DcaStep().run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (3, 6)
    assert sorted(out.labels["metric"].values()) == list(range(6))


def _var_fixture(n=120, seed=20261105):
    rng = np.random.default_rng(seed)
    data = np.zeros((n, 2))
    for i in range(1, n):
        data[i] = [0.5 * data[i - 1, 0] + 0.1 * data[i - 1, 1] + rng.normal(0, 0.4),
                   0.2 * data[i - 1, 0] + 0.4 * data[i - 1, 1] + rng.normal(0, 0.4)]
    return data


def test_var_model_labels_match_flattened_shape(tmp_path):
    data = _var_fixture()
    form = _form(data, ["sample", "feature"],
                 {"sample": {f"s{i}": i for i in range(data.shape[0])},
                  "feature": {"y1": 0, "y2": 1}})
    ctx = _ctx(tmp_path, {"lags": 1, "output": "out"})
    VarModelStep().run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (6, 4)
    assert sorted(out.labels["equation"].values()) == list(range(6))
    assert sorted(out.labels["term"].values()) == list(range(4))


def _distance(values):
    return np.abs(np.subtract.outer(np.asarray(values, dtype=float),
                                    np.asarray(values, dtype=float)))


def test_mantel_returns_column_vector_with_four_statistics(tmp_path):
    a = _distance([0.0, 1.0, 2.5, 4.0])
    b = _distance([0.0, 1.5, 2.0, 5.0])
    labels = {"sample": {f"s{i}": i for i in range(4)},
              "sample_b": {f"s{i}": i for i in range(4)}}
    fa = _form(a, ["sample", "sample_b"], labels)
    fb = _form(b, ["sample", "sample_b"], labels)
    ctx = _ctx(tmp_path, {"n_perm": 99, "random_state": 0, "output": "out"})
    MantelStep().run(ctx, [fa, fb])
    out = ctx["out"]
    assert out.data.shape == (4, 1)
    assert sorted(out.labels["statistic"].values()) == list(range(4))


def test_nestedness_returns_column_vector_with_four_statistics(tmp_path):
    matrix = np.array([[1, 1, 1, 0, 0],
                       [1, 1, 1, 1, 0],
                       [1, 1, 0, 0, 0],
                       [1, 1, 1, 1, 1]], dtype=float)
    form = _form(matrix, ["sample", "taxon"],
                 {"sample": {f"s{i}": i for i in range(4)},
                  "taxon": {f"t{i}": i for i in range(5)}})
    ctx = _ctx(tmp_path, {"output": "out"})
    NestednessStep().run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (4, 1)
    assert sorted(out.labels["statistic"].values()) == list(range(4))
