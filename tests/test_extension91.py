"""Hand-computed checks for the 1.6.0 community-ecology operators.

SIMPER, MRPP and the exact species accumulation curve are compared with
values printed by ``vegan`` for a fixed fixture; the cophenetic
correlation is compared with a hand-built tree whose patristic
distances are known.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers.newick_reader import NewickReader
from src.task.step.steps.cophenetic_correlation import CopheneticCorrelationStep
from src.task.step.steps.mrpp import MrppStep
from src.task.step.steps.simper import SimperStep
from src.task.step.steps.specaccum import SpecaccumStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


COUNTS = np.array([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=float)
GROUPS = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
TAXA = ["t1", "t2", "t3", "t4"]
SAMPLES = [f"s{i}" for i in range(6)]

# vegan::simper(comm, grp, permutations = 0) on COUNTS / GROUPS
R_AVERAGE = [0.375022158911, 0.272657486546, 0.141907249129, 0.034727761950]
R_AVA = [10.0, 1.0, 1.0 / 3.0, 1.0]
R_AVB = [1.0 / 3.0, 8.0, 4.0, 1.0]
R_OVERALL = 0.824314656537

# vegan::mrpp(comm, grp, permutations = 0) on COUNTS / GROUPS
R_DELTA = 2.99132241231
R_EDELTA = 8.75877939551


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _inputs(counts=COUNTS, groups=GROUPS):
    table = _form(
        counts,
        ["sample", "taxon"],
        {
            "sample": {name: index for index, name in enumerate(SAMPLES)},
            "taxon": {name: index for index, name in enumerate(TAXA)},
        },
    )
    meta = _form(
        np.asarray(groups, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {name: index for index, name in enumerate(SAMPLES)},
            "feature": {"group": 0},
        },
    )
    return table, meta


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    out = ctx[params["output"]]
    out.validate()
    return out, step.export(ctx)


def _column(form, name):
    return np.asarray(form.data[form.labels["statistic"][name], :], dtype=float)


def test_simper_matches_vegan_values():
    table, meta = _inputs()
    out, exported = _run(
        SimperStep(),
        {"group_label": "group", "group_a": "0", "group_b": "1", "output": "simper"},
        [table, meta],
    )
    assert list(out.dims) == ["taxon", "statistic"]
    assert list(out.labels["taxon"]) == TAXA
    average = np.asarray(out.data[:, out.labels["statistic"]["average"]], dtype=float)
    assert np.allclose(average, R_AVERAGE, atol=1e-7)
    assert np.allclose(
        np.asarray(out.data[:, out.labels["statistic"]["ava"]], dtype=float), R_AVA, atol=1e-6
    )
    assert np.allclose(
        np.asarray(out.data[:, out.labels["statistic"]["avb"]], dtype=float), R_AVB, atol=1e-6
    )
    assert np.isclose(exported["overall"], R_OVERALL, atol=1e-9)
    cumulative = np.asarray(out.data[:, out.labels["statistic"]["cumsum"]], dtype=float)
    hand = np.cumsum(R_AVERAGE) / R_OVERALL
    assert np.allclose(cumulative, hand, atol=1e-6)
    assert np.isclose(cumulative[-1], 1.0, atol=1e-6)


def test_simper_rejects_bad_groups():
    table, meta = _inputs()
    step = SimperStep()
    with pytest.raises(StepError, match="must differ"):
        _run(step, {"group_label": "group", "group_a": "0", "group_b": "0", "output": "x"},
             [table, meta])
    with pytest.raises(StepError, match="has no samples"):
        _run(step, {"group_label": "group", "group_a": "0", "group_b": "2", "output": "x"},
             [table, meta])


def test_mrpp_matches_vegan_values():
    table, meta = _inputs()
    out, exported = _run(
        MrppStep(),
        {"group_label": "group", "n_perm": 99, "random_state": 7, "output": "mrpp"},
        [table, meta],
    )
    assert np.isclose(exported["delta"], R_DELTA, atol=1e-9)
    assert np.isclose(exported["E_delta"], R_EDELTA, atol=1e-9)
    assert np.isclose(exported["A"], 1.0 - R_DELTA / R_EDELTA, atol=1e-12)
    assert 0.0 < exported["p"] <= 1.0
    assert exported["group_sizes"] == {"0": 3, "1": 3}
    names = list(out.labels["statistic"])
    assert names == ["delta", "E_delta", "A", "p", "n_groups", "n_samples"]


def test_mrpp_permutation_is_seeded():
    table, meta = _inputs()
    params = {"group_label": "group", "n_perm": 99, "random_state": 11, "output": "mrpp"}
    _first, first = _run(MrppStep(), params, [table, meta])
    _second, second = _run(MrppStep(), params, [table, meta])
    assert first["p"] == second["p"]


def test_mrpp_rejects_single_group():
    table, meta = _inputs(groups=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    with pytest.raises(StepError, match="at least two groups"):
        _run(MrppStep(), {"group_label": "group", "output": "mrpp"}, [table, meta])


def test_specaccum_matches_vegan_values():
    table, _meta = _inputs()
    out, exported = _run(
        SpecaccumStep(), {"sample_dim": "sample", "taxon_dim": "taxon", "output": "curve"},
        [table],
    )
    richness = np.asarray(out.data[:, out.labels["statistic"]["richness"]], dtype=float)
    sd = np.asarray(out.data[:, out.labels["statistic"]["sd"]], dtype=float)
    expected = [2.83333333333, 3.8, 4.0, 4.0, 4.0, 4.0]
    assert np.allclose(richness, expected, atol=1e-6)
    assert np.isclose(sd[0], 0.37267799625, atol=1e-6)
    # vegan reports NaN for the exactly-zero variance at i = 2 because its
    # round-off makes the sum slightly negative; the operator clamps to 0.
    assert np.allclose(sd[1:], 0.0, atol=1e-7)
    assert exported["n_sites"] == 6
    assert exported["n_species"] == 4


def test_specaccum_hand_values():
    counts = np.array([[1, 0], [1, 0], [0, 1]], dtype=float)
    table = _form(
        counts,
        ["sample", "taxon"],
        {
            "sample": {f"s{i}": i for i in range(3)},
            "taxon": {f"t{j}": j for j in range(2)},
        },
    )
    out, _exported = _run(SpecaccumStep(), {"output": "curve"}, [table])
    richness = np.asarray(out.data[:, out.labels["statistic"]["richness"]], dtype=float)
    assert np.allclose(richness, [1.0, 5.0 / 3.0, 2.0], atol=1e-6)


def test_specaccum_rejects_empty_and_single_site():
    empty = _form(
        np.zeros((3, 2), dtype=float),
        ["sample", "taxon"],
        {"sample": {f"s{i}": i for i in range(3)}, "taxon": {"a": 0, "b": 1}},
    )
    with pytest.raises(StepError, match="every sample is empty"):
        _run(SpecaccumStep(), {"output": "curve"}, [empty])
    one = _form(
        np.ones((1, 2), dtype=float),
        ["sample", "taxon"],
        {"sample": {"s0": 0}, "taxon": {"a": 0, "b": 1}},
    )
    with pytest.raises(StepError, match="at least two sampling units"):
        _run(SpecaccumStep(), {"output": "curve"}, [one])


def _newick(tmp_path, text):
    path = tmp_path / "tree.nwk"
    path.write_text(text)
    form = NewickReader().read(path, ["node", "field"], {})
    form.validate()
    return form


def _distance_form(values, labels):
    values = np.asarray(values, dtype=float)
    return _form(
        values,
        ["sample", "sample_b"],
        {
            "sample": {name: index for index, name in enumerate(labels)},
            "sample_b": {name: index for index, name in enumerate(labels)},
        },
    )


def test_cophenetic_correlation(tmp_path):
    tree = _newick(tmp_path, "((A:1,B:1):1,(C:2,D:2):2);")
    labels = ["A", "B", "C", "D"]
    observed = _distance_form(
        [[0, 2, 6, 6], [2, 0, 6, 6], [6, 6, 0, 4], [6, 6, 4, 0]], labels
    )
    out, exported = _run(
        CopheneticCorrelationStep(),
        {"output": "cophenetic_correlation"},
        [tree, observed],
    )
    assert np.isclose(exported["r"], 1.0, atol=1e-12)
    assert np.isclose(exported["r_squared"], 1.0, atol=1e-12)
    assert exported["n_tips"] == 4
    assert exported["n_pairs"] == 6

    perturbed = _distance_form(
        [[0, 2, 5, 6], [2, 0, 6, 6], [5, 6, 0, 4], [6, 6, 4, 0]], labels
    )
    _out2, exported2 = _run(
        CopheneticCorrelationStep(),
        {"output": "cophenetic_correlation"},
        [tree, perturbed],
    )
    x = np.array([2.0, 6.0, 6.0, 6.0, 6.0, 4.0])
    y = np.array([2.0, 5.0, 6.0, 6.0, 6.0, 4.0])
    assert np.isclose(exported2["r"], float(np.corrcoef(x, y)[0, 1]), atol=1e-12)


def test_cophenetic_rejects_mismatched_taxa(tmp_path):
    tree = _newick(tmp_path, "((A:1,B:1):1,(C:2,D:2):2);")
    observed = _distance_form(
        np.zeros((3, 3)),
        ["A", "B", "C"],
    )
    with pytest.raises(StepError, match="differ"):
        _run(
            CopheneticCorrelationStep(),
            {"output": "cophenetic_correlation"},
            [tree, observed],
        )


def test_cophenetic_rejects_constant_tree(tmp_path):
    tree = _newick(tmp_path, "(A:0,B:0,C:0);")
    observed = _distance_form([[0, 1, 1], [1, 0, 1], [1, 1, 0]], ["A", "B", "C"])
    with pytest.raises(StepError, match="constant"):
        _run(
            CopheneticCorrelationStep(),
            {"output": "cophenetic_correlation"},
            [tree, observed],
        )
