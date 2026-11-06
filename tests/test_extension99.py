"""Tests for 1.14.0 discriminant, correspondence, nestedness and Renyi operators."""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.corresp import CorrespStep
from src.task.step.steps.lda import LdaStep
from src.task.step.steps.nestedness import NestednessStep
from src.task.step.steps.renyi import RenyiStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _form(data, dims, labels, info=None):
    form = Form(data=np.asarray(data, dtype=np.float32), dims=list(dims),
                labels=labels, info=info or {"missing_code": np.nan})
    form.validate()
    return form


def _lda_inputs():
    x1 = [1, 2, 2, 3, 5, 6, 6, 7, 9, 9, 10, 11]
    x2 = [2, 1, 3, 4, 9, 8, 10, 9, 1, 2, 1, 3]
    groups = [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2]
    samples = [f"s{i}" for i in range(12)]
    features = _form(np.column_stack([x1, x2]).astype(float),
                     ["sample", "feature"],
                     {"sample": {s: i for i, s in enumerate(samples)},
                      "feature": {"x1": 0, "x2": 1}})
    labels = _form(np.asarray(groups, dtype=float)[:, None],
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "label": {"g": 0}})
    return features, labels


def test_lda_matches_r_reference():
    features, labels = _lda_inputs()
    out, export = _run(LdaStep(), (features, labels), {"target_label": "g"})
    assert export["accuracy"] == 1.0
    assert export["confusion_matrix"] == [[4, 0, 0], [0, 4, 0], [0, 0, 4]]
    np.testing.assert_allclose(export["priors"], [1 / 3, 1 / 3, 1 / 3], atol=1e-12)
    np.testing.assert_allclose(export["svd"], [11.8406893841126, 6.51204810801763],
                               rtol=1e-9)
    means = np.asarray(out.info["means"])
    np.testing.assert_allclose(means, [[2, 2.5], [6, 9], [9.75, 1.75]], atol=1e-12)
    scaling = np.asarray(out.info["scaling"])
    expected = np.asarray([[1.18881463854869, -0.531386797996899],
                           [-0.849304331273455, -0.672751957528487]])
    np.testing.assert_allclose(scaling, expected, rtol=1e-9)
    assert out.dims == ["sample", "statistic"]
    ld_columns = [name for name in out.labels["statistic"] if name.startswith("LD")]
    assert ld_columns == ["LD1", "LD2"]
    scores = out.data[:, 3:]
    first_ld1 = np.asarray([-3.792519839, -1.7544008691, -3.4530095317,
                            -3.1134992244])
    first_ld2 = np.asarray([4.2384689875, 4.379834147, 3.034330232,
                            1.8301914765])
    np.testing.assert_allclose(scores[:4, 0], first_ld1, atol=1e-5)
    np.testing.assert_allclose(scores[:4, 1], first_ld2, atol=1e-5)
    assert "posterior" not in out.labels["statistic"]


def test_lda_rejects_single_class():
    features, _ = _lda_inputs()
    samples = [f"s{i}" for i in range(12)]
    labels = _form(np.zeros((12, 1)),
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "label": {"g": 0}})
    with pytest.raises(StepError, match="at least two classes"):
        LdaStep().run(Ctx({"target_label": "g"}), (features, labels))


def test_lda_rejects_constant_feature():
    samples = [f"s{i}" for i in range(6)]
    features = _form([[0, 1], [0, 2], [0, 3], [1, 4], [1, 5], [1, 6]],
                     ["sample", "feature"],
                     {"sample": {s: i for i, s in enumerate(samples)},
                      "feature": {"x1": 0, "x2": 1}})
    labels = _form([[0], [0], [0], [1], [1], [1]],
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "label": {"g": 0}})
    with pytest.raises(StepError, match="constant within groups"):
        LdaStep().run(Ctx({"target_label": "g"}), (features, labels))


def _corresp_form():
    table = [[10, 5, 0], [2, 8, 4], [0, 3, 7]]
    return _form(table, ["row", "column"],
                 {"row": {"A": 0, "B": 1, "C": 2},
                  "column": {"X": 0, "Y": 1, "Z": 2}})


def _align(scores, reference):
    aligned = np.array(scores, dtype=float)
    reference = np.asarray(reference, dtype=float)
    for j in range(aligned.shape[1]):
        pivot = int(np.argmax(np.abs(reference[:, j])))
        if np.sign(aligned[pivot, j]) != np.sign(reference[pivot, j]):
            aligned[:, j] *= -1.0
    return aligned


def test_corresp_matches_mass_reference():
    out, export = _run(CorrespStep(), (_corresp_form(),), {"n_components": 2})
    reference = [[-1.1667810751848353, 0.4884894293539225],
                 [0.3131763718668609, -1.2990900068196187],
                 [1.3117246921636476, 1.0859918655165812]]
    rows = _align(out.data, reference)
    np.testing.assert_allclose(rows, reference, atol=1e-6)
    columns = np.asarray(out.info["column_scores"])
    column_reference = [[-1.28228298158434217, 0.7782996563915278],
                        [0.05284186807103439, -1.1977928606310708],
                        [1.32199326271595918, 0.8931899903089814]]
    np.testing.assert_allclose(_align(columns, column_reference),
                               column_reference, atol=1e-6)
    np.testing.assert_allclose(out.info["eigenvalues"],
                               [0.717565088120682, 0.244840816464574], atol=1e-9)
    assert export["total_inertia"] == pytest.approx(0.5748466810966811, abs=1e-9)
    assert out.info["column_labels"] == ["X", "Y", "Z"]


def test_corresp_rejects_empty_row():
    table = [[1, 2], [0, 0]]
    form = _form(table, ["row", "column"],
                 {"row": {"a": 0, "b": 1}, "column": {"x": 0, "y": 1}})
    with pytest.raises(StepError, match="empty row or column"):
        CorrespStep().run(Ctx({}), (form,))


def test_corresp_rejects_negative():
    form = _form([[1, -1], [2, 3]], ["row", "column"],
                 {"row": {"a": 0, "b": 1}, "column": {"x": 0, "y": 1}})
    with pytest.raises(StepError, match="non-negative"):
        CorrespStep().run(Ctx({}), (form,))


def _nestedness_form():
    matrix = [[1, 1, 1, 0, 0],
              [1, 1, 0, 0, 0],
              [1, 1, 1, 1, 0],
              [1, 0, 0, 0, 0],
              [1, 1, 1, 0, 1],
              [0, 0, 0, 0, 0]]
    return _form(matrix, ["sample", "taxon"],
                 {"sample": {f"s{i + 1}": i for i in range(6)},
                  "taxon": {f"t{i + 1}": i for i in range(5)}})


def test_nestedness_matches_vegan_reference():
    out, export = _run(NestednessStep(), (_nestedness_form(),))
    values = out.data[:, 0]
    np.testing.assert_allclose(values, [90.0, 60.0, 72.0, 0.4666666666666667],
                               atol=1e-6)
    assert export["N.columns"] == pytest.approx(90.0, abs=1e-9)
    assert export["N.rows"] == pytest.approx(60.0, abs=1e-9)
    assert export["NODF"] == pytest.approx(72.0, abs=1e-9)
    assert export["fill"] == pytest.approx(0.4666666666666667, abs=1e-9)


def test_nestedness_rejects_empty_matrix():
    form = _form([[0, 0], [0, 0]], ["sample", "taxon"],
                 {"sample": {"a": 0, "b": 1}, "taxon": {"x": 0, "y": 1}})
    with pytest.raises(StepError, match="no occupied cells"):
        NestednessStep().run(Ctx({}), (form,))


def _renyi_form():
    matrix = [[10, 1, 0, 2],
              [8, 2, 1, 0],
              [12, 0, 0, 1],
              [0, 9, 3, 1],
              [1, 8, 4, 0],
              [0, 7, 5, 2]]
    return _form(matrix, ["sample", "taxon"],
                 {"sample": {f"s{i + 1}": i for i in range(6)},
                  "taxon": {f"t{i + 1}": i for i in range(4)}})


def test_renyi_matches_vegan_reference():
    out, _ = _run(RenyiStep(), (_renyi_form(),),
                  {"scales": [0, 0.5, 1, 2], "include_inf": True})
    reference = [
        [1.0986122886681098, 0.8721701734238497, 0.6870920273799715, 0.4759383647655500, 0.2623642645],
        [1.0986122886681098, 0.9157553658363677, 0.7595473914748635, 0.5616840409994818, 0.3184537311],
        [0.6931471805599453, 0.4271866186737351, 0.2711893730418441, 0.1531649725024989, 0.0800427077],
        [1.0986122886681098, 0.9271973900850049, 0.7902679680745903, 0.6190392084062235, 0.3677247801],
        [1.0986122886681098, 0.9605449906166353, 0.8587409130062869, 0.7354495602506346, 0.4855078158],
        [1.0986122886681098, 1.0407821280824716, 0.9922819748525739, 0.9214058325409255, 0.6931471806],
    ]
    np.testing.assert_allclose(out.data, reference, atol=1e-6)
    assert list(out.labels["scale"]) == ["0", "0.5", "1", "2", "Inf"]


def test_renyi_hill_numbers():
    out, _ = _run(RenyiStep(), (_renyi_form(),),
                  {"scales": [0, 1], "include_inf": False, "hill": True})
    np.testing.assert_allclose(
        out.data[:, 0],
        np.exp([math.log(3), math.log(3), math.log(2), math.log(3),
                math.log(3), math.log(3)]),
        atol=1e-6)
    assert out.info["hill"] is True


def test_renyi_rejects_bad_scales():
    with pytest.raises(StepError, match="non-empty list"):
        RenyiStep().run(Ctx({"scales": "all"}),
                        (_renyi_form(),))
