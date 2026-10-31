from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.envfit import EnvfitStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(params, inputs):
    ctx = Ctx(params)
    step = EnvfitStep()
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _fixture():
    rng = np.random.default_rng(20261119)
    n = 30
    ordination = np.column_stack([np.linspace(-2, 2, n), rng.normal(size=n)])
    environment = np.column_stack([
        0.8 * ordination[:, 0] - 0.2 * ordination[:, 1] + rng.normal(scale=0.4, size=n),
        -0.3 * ordination[:, 0] + 0.7 * ordination[:, 1] + rng.normal(scale=0.5, size=n),
        rng.normal(size=n),
    ])
    samples = [f"s{i}" for i in range(n)]
    fx = _form(
        ordination,
        ["sample", "component"],
        {"sample": _labels(samples), "component": _labels(["axis1", "axis2"])},
    )
    fy = _form(
        environment,
        ["sample", "feature"],
        {"sample": _labels(samples), "feature": _labels(["e1", "e2", "e3"])},
    )
    return fx, fy


def test_envfit_matches_vegan_reference():
    fx, fy = _fixture()
    out, info = _run({}, [fx, fy])
    assert info["n"] == 30
    assert info["n_components"] == 2
    assert info["n_features"] == 3
    assert info["permutations"] == 0
    assert out.data.shape == (3, 3)
    assert out.dims == ["feature", "statistic"]
    assert list(out.labels["feature"]) == ["e1", "e2", "e3"]
    expected_r2 = [0.8558115299, 0.7321193529, 0.0225284919]
    expected_arrows = [
        [0.9543868304, -0.2985728943],
        [-0.3895471426, 0.9210065355],
        [-0.7772594457, -0.6291802222],
    ]
    for i, feature in enumerate(["e1", "e2", "e3"]):
        assert info["r2"][feature] == pytest.approx(expected_r2[i], abs=5e-7)
        assert info["arrows"][feature] == pytest.approx(expected_arrows[i], abs=5e-7)
        row = out.data[i]
        assert row[0] == pytest.approx(expected_r2[i], abs=5e-6)
        assert row[1] == pytest.approx(expected_arrows[i][0], abs=5e-6)
        assert row[2] == pytest.approx(expected_arrows[i][1], abs=5e-6)


def test_envfit_aligns_by_labels_and_drops_nonfinite_rows():
    fx, fy = _fixture()
    # Reverse the environment rows; sample labels must keep the pairing.
    reversed_data = fy.data[::-1]
    fy_rev = _form(
        reversed_data,
        ["sample", "feature"],
        {
            "sample": {name: i for i, name in enumerate(list(fy.labels["sample"])[::-1])},
            "feature": fy.labels["feature"],
        },
    )
    out_a, info_a = _run({}, [fx, fy])
    out_b, info_b = _run({}, [fx, fy_rev])
    assert info_b["r2"] == pytest.approx(info_a["r2"], abs=5e-6)
    assert out_b.data == pytest.approx(out_a.data, abs=5e-6)

    broken = np.array(fy.data, copy=True)
    broken[4, 1] = np.nan
    fy_broken = _form(
        broken,
        ["sample", "feature"],
        {"sample": fy.labels["sample"], "feature": fy.labels["feature"]},
    )
    out_c, info_c = _run({}, [fx, fy_broken])
    assert info_c["n"] == 29
    assert out_c.data.shape == (3, 3)


def test_envfit_rejects_invalid_inputs():
    fx, fy = _fixture()
    with pytest.raises(StepError, match="at least 2 ordination components"):
        _run({}, [_form(fx.data[:, :1], ["sample", "component"],
                        {"sample": fx.labels["sample"], "component": {"axis1": 0}}), fy])

    constant = np.zeros((30, 1), dtype=np.float32)
    fy_const = _form(
        constant,
        ["sample", "feature"],
        {"sample": fy.labels["sample"], "feature": {"bad": 0}},
    )
    with pytest.raises(StepError, match="zero variance"):
        _run({}, [fx, fy_const])

    with pytest.raises(StepError, match="shared samples"):
        _run({}, [_form(fx.data, ["sample", "component"],
                         {"sample": _labels([f"x{i}" for i in range(30)]),
                          "component": fx.labels["component"]}), fy])
