import numpy as np
from src.core import Form
from src.task.step.steps.brunner_munzel import BrunnerMunzelStep
from src.task.step.steps.fligner_kruskal import FlignerKruskalStep
from src.task.step.steps.jarque_bera import JarqueBeraStep
from src.task.step.steps.ks_2samp import Ks2SampStep
from src.task.step.steps.permutation_test import PermutationTestStep
from src.task.step.steps.sign_test import SignTestStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels, {"missing_code": np.nan})
    value.validate()
    return value


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _matrix(n=12, p=4, seed=41):
    rng = np.random.default_rng(seed)
    return _form(
        rng.normal(size=(p, n)),
        ["feature", "sample"],
        {"feature": {f"f{i}": i for i in range(p)}, "sample": {f"s{i}": i for i in range(n)}},
    )


def _grouped(n_groups=2, per_group=6, p=2, seed=43):
    n = n_groups * per_group
    rng = np.random.default_rng(seed)
    features = _form(
        rng.normal(size=(p, n)),
        ["feature", "sample"],
        {"feature": {f"f{i}": i for i in range(p)}, "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        np.asarray([[i // per_group] for i in range(n)], dtype=object),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        dtype=object,
    )
    return features, meta


def test_ks_and_brunner_munzel():
    features, meta = _grouped()
    for step, labels in ((Ks2SampStep(), {"KS": 0, "P": 1}), (BrunnerMunzelStep(), {"W": 0, "P": 1})):
        out, export = _run(step, {"group_label": "group"}, [features, meta])
        assert out.data.shape == (2, 2)
        assert out.labels["statistic"] == labels
        assert np.isfinite(out.data).all()
        assert export["n_groups"] == 2


def test_fligner_three_groups():
    features, meta = _grouped(n_groups=3, per_group=4, p=3)
    out, export = _run(FlignerKruskalStep(), {"group_label": "group"}, [features, meta])
    assert out.data.shape == (3, 2)
    assert out.labels["statistic"] == {"W": 0, "P": 1}
    assert np.isfinite(out.data).all()
    assert export["n_groups"] == 3


def test_sign_and_permutation():
    features, meta = _grouped(per_group=6, p=2)
    sign, export = _run(SignTestStep(), {"group_label": "group"}, [features, meta])
    assert sign.data.shape == (2, 3)
    assert sign.labels["statistic"] == {"POS": 0, "NEG": 1, "P": 2}
    assert export["n_groups"] == 2

    features, meta = _grouped(per_group=6, p=2, seed=47)
    perm, export = _run(
        PermutationTestStep(),
        {"group_label": "group", "n_perm": 50, "random_state": 1},
        [features, meta],
    )
    assert perm.data.shape == (2, 2)
    assert perm.labels["statistic"] == {"D": 0, "P": 1}
    assert np.isfinite(perm.data).all()
    assert export["n_groups"] == 2


def test_jarque_bera():
    out, export = _run(JarqueBeraStep(), {}, [_matrix(n=16, p=3)])
    assert out.data.shape == (3, 2)
    assert out.labels["statistic"] == {"JB": 0, "P": 1}
    assert np.isfinite(out.data).all()
    assert export["n_features"] == 3
