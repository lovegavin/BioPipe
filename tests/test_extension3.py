from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.bedgraph_reader import BedGraphReader
from src.reader.readers.excel_reader import ExcelReader
from src.reader.readers.fai_reader import FaiReader
from src.reader.readers.gct_reader import GctReader
from src.reader.readers.json_table_reader import JsonTableReader
from src.reader.readers.narrowpeak_reader import NarrowPeakReader
from src.reader.readers.npy_reader import NpyReader
from src.task.step.steps._matrix_common import matrix
from src.task.step.steps.ada_boost_classifier import AdaBoostClassifierStep
from src.task.step.steps.ada_boost_regressor import AdaBoostRegressorStep
from src.task.step.steps.anova import AnovaStep
from src.task.step.steps.chi_square import ChiSquareStep
from src.task.step.steps.decision_tree_classifier import DecisionTreeClassifierStep
from src.task.step.steps.decision_tree_regressor import DecisionTreeRegressorStep
from src.task.step.steps.extra_trees_classifier import ExtraTreesClassifierStep
from src.task.step.steps.extra_trees_regressor import ExtraTreesRegressorStep
from src.task.step.steps.fisher_exact import FisherExactStep
from src.task.step.steps.kruskal import KruskalStep
from src.task.step.steps.lda_classifier import LdaClassifierStep
from src.task.step.steps.levene import LeveneStep
from src.task.step.steps.multinomial_nb_classifier import MultinomialNBClassifierStep
from src.task.step.steps.complement_nb_classifier import ComplementNBClassifierStep
from src.task.step.steps.nmf import NmfStep
from src.task.step.steps.shapiro import ShapiroStep
from src.task.step.steps.sgd_classifier import SgdClassifierStep
from src.task.step.steps.sgd_regressor import SgdRegressorStep
from src.task.step.steps.tsne import TsneStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels,
                 {"missing_code": np.nan})
    value.validate()
    return value


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _ml_forms(n=30, p=6, classification=True):
    rng = np.random.default_rng(7)
    data = rng.uniform(0.2, 4.0, size=(n, p)).astype(np.float32)
    features = _form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {f"f{i}": i for i in range(p)}},
    )
    if classification:
        y = (np.arange(n) % 2).astype(np.float32)
    else:
        y = rng.normal(size=n).astype(np.float32)
    labels = _form(
        y.reshape(-1, 1),
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(n)}, "label": {"y": 0}},
    )
    return features, labels


ML_CLASSIFIERS = [
    DecisionTreeClassifierStep,
    ExtraTreesClassifierStep,
    AdaBoostClassifierStep,
    ComplementNBClassifierStep,
    MultinomialNBClassifierStep,
    LdaClassifierStep,
    SgdClassifierStep,
]
ML_REGRESSORS = [
    DecisionTreeRegressorStep,
    ExtraTreesRegressorStep,
    AdaBoostRegressorStep,
    SgdRegressorStep,
]


@pytest.mark.parametrize("step_cls", ML_CLASSIFIERS)
def test_new_classifier_operators_run(step_cls):
    features, labels = _ml_forms(classification=True)
    params = {"target_label": "y", "test_size": 0.25, "cv_folds": 3}
    if step_cls in (ComplementNBClassifierStep, MultinomialNBClassifierStep):
        params["scale"] = False
    out, export = _run(step_cls(), params, [features, labels])
    assert out.data.ndim == 2
    assert export["test_accuracy"] >= 0.0
    assert np.isfinite(out.data).all()


@pytest.mark.parametrize("step_cls", ML_REGRESSORS)
def test_new_regressor_operators_run(step_cls):
    features, labels = _ml_forms(classification=False)
    out, export = _run(
        step_cls(),
        {"target_label": "y", "test_size": 0.25, "cv_folds": 3},
        [features, labels],
    )
    assert out.data.ndim == 2
    assert np.isfinite(export["test_r2"])
    assert np.isfinite(out.data).all()


def _matrix_forms(n=12, p=5):
    rng = np.random.default_rng(11)
    data = rng.uniform(0.5, 3.0, size=(p, n)).astype(np.float32)
    features = _form(
        data,
        ["feature", "sample"],
        {"feature": {f"f{i}": i for i in range(p)},
         "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        np.array([[i % 3] for i in range(n)], dtype=object),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        dtype=object,
    )
    return features, meta


def test_projection_and_group_test_operators():
    features, meta = _matrix_forms()
    for step, params in [
        (TsneStep(), {"perplexity": 3, "n_components": 2}),
        (NmfStep(), {"n_components": 2}),
    ]:
        out, export = _run(step, params, [features])
        assert out.data.shape[0] == 12
        assert out.dims[0] == "sample"
        assert np.isfinite(out.data).all()
        assert export["n_samples"] == 12
    for step in (AnovaStep(), KruskalStep(), LeveneStep()):
        out, export = _run(step, {"group_label": "group"}, [features, meta])
        assert out.data.shape[0] == 5
        assert out.labels["statistic"] in ({"F": 0, "P": 1}, {"H": 0, "P": 1}, {"W": 0, "P": 1})
        assert np.isfinite(out.data).all()
        assert export["n_groups"] == 3
    shapiro, _ = _run(ShapiroStep(), {}, [features])
    assert shapiro.data.shape == (5, 2)
    assert np.isfinite(shapiro.data).all()


def test_contingency_tests():
    table = _form([[10, 5], [3, 12]], ["row", "col"],
                  {"row": {"a": 0, "b": 1}, "col": {"x": 0, "y": 1}})
    chi, chi_export = _run(ChiSquareStep(), {}, [table])
    assert chi.data.shape == (1, 4)
    assert chi.labels["statistic"]["P"] == 1
    assert 0.0 <= chi_export["p"] <= 1.0
    fisher, fisher_export = _run(FisherExactStep(), {}, [table])
    assert fisher.data.shape == (1, 2)
    assert fisher_export["odds_ratio"] > 0
    assert 0.0 <= fisher_export["p"] <= 1.0


def test_matrix_helper_reorients_and_fills_missing():
    form = _form([[1.0, np.nan], [3.0, 4.0]], ["feature", "sample"],
                 {"feature": {"f0": 0, "f1": 1}, "sample": {"s0": 0, "s1": 1}})
    X, samples, features = matrix(form, "sample", "feature")
    assert X.shape == (2, 2)
    assert samples == ["s0", "s1"]
    assert features == ["f0", "f1"]
    assert np.isfinite(X).all()


def test_excel_reader_round_trip(tmp_path):
    path = tmp_path / "table.xlsx"
    pd.DataFrame({"s1": [1.0, 2.0], "s2": [3.0, 4.0]}).to_excel(path, sheet_name="expr", index=False)
    form = ExcelReader().read(path, ["sample", "feature"], {"feature": "builtin"},
                              sheet="expr")
    assert form.dims == ["sample", "feature"]
    assert form.data.shape == (2, 2)
    assert list(form.labels["feature"]) == ["s1", "s2"]


def test_gct_reader_transposes_to_sample_by_gene(tmp_path):
    path = tmp_path / "expr.gct"
    path.write_text(
        "#1.2\n2 2\nName\tDescription\ts1\ts2\n"
        "g1\tdesc1\t1\t2\ng2\tdesc2\t3\t4\n",
        encoding="utf-8",
    )
    form = GctReader().read(path, ["sample", "gene"], {})
    assert form.data.tolist() == [[1, 3], [2, 4]]
    assert list(form.labels["sample"]) == ["s1", "s2"]
    assert list(form.labels["gene"]) == ["g1", "g2"]
    assert form.info["gene_description"]["g1"] == "desc1"


def test_bedgraph_and_narrowpeak_readers(tmp_path):
    bedgraph = tmp_path / "track.bedgraph"
    bedgraph.write_text("chr1\t0\t10\t1.5\nchr1\t10\t20\t2.5\n", encoding="utf-8")
    bg = BedGraphReader().read(bedgraph, ["region", "field"], {})
    assert bg.data.shape == (2, 4)
    assert list(bg.labels["field"]) == ["chrom", "start", "end", "value"]
    narrow = tmp_path / "peak.narrowPeak"
    narrow.write_text(
        "chr1\t0\t10\tp1\t100\t+\t3.0\t2.0\t1.5\t5\n",
        encoding="utf-8",
    )
    npk = NarrowPeakReader().read(narrow, ["region", "field"], {})
    assert npk.data.shape == (1, 10)
    assert list(npk.labels["field"])[:4] == ["chrom", "start", "end", "name"]


def test_npy_reader_npy_and_npz(tmp_path):
    npy = tmp_path / "matrix.npy"
    np.save(npy, np.arange(6, dtype=np.float32).reshape(2, 3))
    form = NpyReader().read(npy, ["sample", "feature"], {})
    assert form.data.shape == (2, 3)
    assert list(form.labels["sample"]) == ["0", "1"]
    npz = tmp_path / "matrix.npz"
    np.savez(npz, expr=np.arange(6, dtype=np.float32).reshape(3, 2))
    form = NpyReader().read(npz, ["sample", "feature"], {"key": "expr"})
    assert form.data.shape == (3, 2)


def test_json_and_fai_readers(tmp_path):
    path = tmp_path / "table.json"
    path.write_text(json.dumps([{"a": 1, "b": 2}, {"a": 3, "b": 4}]),
                    encoding="utf-8")
    form = JsonTableReader().read(path, ["sample", "feature"], {})
    assert form.data.shape == (2, 2)
    assert list(form.labels["feature"]) == ["a", "b"]
    fai = tmp_path / "genome.fai"
    fai.write_text("chr1\t1000\t6\t60\t61\nchr2\t500\t1010\t50\t51\n",
                    encoding="utf-8")
    f = FaiReader().read(fai, ["record", "field"], {})
    assert f.data.shape == (2, 5)
    assert list(f.labels["field"]) == ["name", "length", "offset", "linebases", "linewidth"]


def test_gct_reader_accepts_missing_tokens(tmp_path):
    path = tmp_path / "expr_missing.gct"
    path.write_text(
        "#1.2\n2 2\nName\tDescription\ts1\ts2\n"
        "g1\tdesc1\t1\tNA\ng2\tdesc2\t\t4\n",
        encoding="utf-8",
    )
    form = GctReader().read(path, ["sample", "gene"], {})
    assert form.data.shape == (2, 2)
    assert form.data[0, 0] == 1
    assert np.isnan(form.data[0, 1])
    assert np.isnan(form.data[1, 0])
    assert form.data[1, 1] == 4
    assert isinstance(pick_reader(path), GctReader)
