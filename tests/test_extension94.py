import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.glmm_logistic import GlmmLogisticStep
from src.task.step.steps.knn import KnnStep
from src.task.step.steps.manova import ManovaStep
from src.task.step.steps.qda import QdaStep, _fit, _log_posterior


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _form(data, dims, labels, encoders=None):
    info = {"missing_code": np.nan}
    if encoders:
        info["encoders"] = encoders
    form = Form(data=np.asarray(data, dtype=float), dims=dims, labels=labels,
                info=info)
    form.validate()
    return form


MANOVA_Y1 = [2.1, 1.8, 2.4, 2.0, 1.9, 4.2, 4.0, 4.6, 3.8, 4.4,
             6.1, 5.8, 6.4, 6.0, 5.9]
MANOVA_Y2 = [1.0, 1.4, 0.9, 1.2, 1.1, 2.2, 2.5, 2.0, 2.3, 2.1,
             3.3, 3.6, 3.1, 3.4, 3.2]


def manova_inputs():
    samples = [f"s{i}" for i in range(15)]
    values = _form(np.column_stack([MANOVA_Y1, MANOVA_Y2]),
                   ["sample", "response"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "response": {"y1": 0, "y2": 1}})
    codes = [0] * 5 + [1] * 5 + [2] * 5
    encoder = get_encoder("labelencoder")
    encoder.fit_transform(["a", "b", "c"])
    meta = _form(np.array(codes, dtype=float)[:, None],
                 ["sample", "feature"],
                 {"sample": {s: i for i, s in enumerate(samples)},
                  "feature": {"group": 0}},
                 encoders={"feature": {"group": encoder}})
    return values, meta


@pytest.mark.parametrize("test,value,f_value,num_df,den_df,p_value", [
    ("pillai", 1.017952614, 6.219369380, 4.0, 24.0, 0.001396238),
    ("wilks", 0.002533941, 103.760804, 4.0, 22.0, 6.019293e-14),
    ("hotelling_lawley", 385.557254, 963.893134, 4.0, 20.0, 1.466533e-22),
    ("roy", 385.536283, 2313.217749, 2.0, 12.0, 2.998185e-16),
])
def test_manova_matches_r(test, value, f_value, num_df, den_df, p_value):
    values, meta = manova_inputs()
    out, export = run(ManovaStep(), (values, meta),
                      {"group_label": "group", "test": test,
                       "output": "output"})
    data = np.asarray(out.data, dtype=np.float64).ravel()
    assert data[1] == pytest.approx(value, rel=1e-6)
    assert data[2] == pytest.approx(f_value, rel=1e-6)
    assert data[3] == pytest.approx(num_df, abs=1e-9)
    assert data[4] == pytest.approx(den_df, abs=1e-9)
    assert data[5] == pytest.approx(p_value, rel=1e-4)
    assert export["test"] == test


def test_manova_requires_two_groups():
    values, meta = manova_inputs()
    encoder = get_encoder("labelencoder")
    encoder.fit_transform(["a"] * 15)
    single = _form(np.zeros((15, 1)), ["sample", "feature"],
                   {"sample": meta.labels["sample"], "feature": {"group": 0}},
                   encoders={"feature": {"group": encoder}})
    with pytest.raises(StepError, match="at least two groups"):
        run(ManovaStep(), (values, single),
            {"group_label": "group", "output": "output"})


def test_qda_means_and_posteriors_match_r():
    x = np.array([[0.2, 0.4], [0.5, 0.1], [0.3, 0.6], [0.8, 0.2],
                  [0.1, 0.5], [2.0, 1.1], [2.4, 1.4], [2.2, 1.2],
                  [2.6, 1.5], [2.1, 1.3], [4.1, 3.1], [4.5, 3.5],
                  [4.3, 3.3], [4.7, 3.6], [4.2, 3.2]])
    y = np.array(["p"] * 5 + ["q"] * 5 + ["r"] * 5)
    classes, means, covs, priors = _fit(x, y, 0.0)
    assert list(classes) == ["p", "q", "r"]
    assert means == pytest.approx(
        np.array([[0.38, 0.36], [2.26, 1.3], [4.36, 3.34]]), abs=1e-12
    )
    assert priors == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    test = np.array([[0.4, 0.3], [2.2, 1.3], [4.4, 3.4], [1.0, 2.5]])
    assert _log_posterior(test, means, covs, priors).argmax(axis=1).tolist() == [
        0, 1, 2, 0
    ]


def test_qda_step_runs_on_fixture():
    samples = [f"s{i}" for i in range(18)]
    x = np.array([[0.2, 0.4], [0.5, 0.1], [0.3, 0.6], [0.8, 0.2],
                  [0.1, 0.5], [0.6, 0.3],
                  [2.0, 1.1], [2.4, 1.4], [2.2, 1.2], [2.6, 1.5],
                  [2.1, 1.3], [2.3, 1.6],
                  [4.1, 3.1], [4.5, 3.5], [4.3, 3.3], [4.7, 3.6],
                  [4.2, 3.2], [4.0, 3.9]])
    encoder = get_encoder("labelencoder")
    codes = encoder.fit_transform(["p"] * 6 + ["q"] * 6 + ["r"] * 6)
    enc = {"label": {"kind": encoder}}
    features = _form(x, ["sample", "feature"],
                     {"sample": {s: i for i, s in enumerate(samples)},
                      "feature": {"x1": 0, "x2": 1}})
    labels = _form(np.array(codes, dtype=float)[:, None],
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "label": {"kind": 0}}, encoders=enc)
    out, export = run(QdaStep(), (features, labels),
                      {"target_label": "kind", "test_size": 0.33,
                       "random_state": 0, "output": "output"})
    assert out.dims == ["sample", "statistic"]
    assert export["test_accuracy"] >= 0.8
    assert export["classes"] == ["p", "q", "r"]


def test_knn_step_predicts_neighbourhoods():
    samples = [f"s{i}" for i in range(15)]
    x = np.array([[0.0, 0.0], [1.0, 0.1], [0.2, 0.3], [0.5, 0.2],
                  [0.1, 0.6], [0.3, 0.1],
                  [3.0, 3.0], [3.2, 3.2], [2.8, 2.9], [3.1, 2.8],
                  [2.9, 3.1], [3.3, 3.0]])
    encoder = get_encoder("labelencoder")
    codes = encoder.fit_transform(["a"] * 6 + ["b"] * 6)
    enc = {"label": {"kind": encoder}}
    features = _form(x, ["sample", "feature"],
                     {"sample": {s: i for i, s in enumerate(samples[:12])},
                      "feature": {"x1": 0, "x2": 1}})
    labels = _form(np.array(codes, dtype=float)[:, None],
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples[:12])},
                    "label": {"kind": 0}}, encoders=enc)
    out, export = run(KnnStep(), (features, labels),
                      {"target_label": "kind", "n_neighbors": 3,
                       "test_size": 0.3, "random_state": 0,
                       "output": "output"})
    assert export["test_accuracy"] >= 0.8
    assert export["n_neighbors"] == 3


def _glmm_inputs(seed=11, ng=20, ni=8):
    rng = np.random.default_rng(seed)
    g = np.repeat(np.arange(ng), ni)
    x = rng.normal(size=ng * ni)
    u = rng.normal(scale=0.7, size=ng)[g]
    y = rng.binomial(1, 1 / (1 + np.exp(-(0.5 + x + u))))
    samples = [f"o{i}" for i in range(ng * ni)]
    table = _form(np.column_stack([y, x]), ["sample", "feature"],
                  {"sample": {s: i for i, s in enumerate(samples)},
                   "feature": {"y": 0, "x": 1}})
    meta = _form(np.array([g], dtype=float).T, ["sample", "feature"],
                 {"sample": {s: i for i, s in enumerate(samples)},
                  "feature": {"grp": 0}})
    return table, meta


def test_glmm_logistic_matches_r():
    table, meta = _glmm_inputs()
    out, export = run(GlmmLogisticStep(), (table, meta),
                      {"target_label": "y", "predictor_label": "x",
                       "group_label": "grp", "output": "output"})
    assert export["coef"]["(Intercept)"] == pytest.approx(0.6449879, abs=1e-3)
    assert export["coef"]["x"] == pytest.approx(0.8022453, abs=1e-3)
    assert export["sigma"] == pytest.approx(0.3134389, abs=1e-3)
    assert export["loglik"] == pytest.approx(-95.1091933, abs=1e-3)
    assert out.dims == ["term", "statistic"]


def test_glmm_rejects_constant_predictor():
    table, meta = _glmm_inputs()
    table.data[:, 1] = 1.0
    with pytest.raises(StepError, match="predictor is constant"):
        run(GlmmLogisticStep(), (table, meta),
            {"target_label": "y", "predictor_label": "x",
             "group_label": "grp", "output": "output"})
