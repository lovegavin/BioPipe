from __future__ import annotations

import h5py
import numpy as np
import pytest

from src.core import Form
from src.reader.readers.fastq_reader import FastqReader
from src.reader.readers.h5_reader import H5Reader
from src.reader.readers.map_reader import MapReader
from src.reader.readers.newick_reader import NewickReader
from src.reader.readers.phylip_reader import PhylipReader
from src.reader.readers.stockholm_reader import StockholmReader
from src.task.step.steps.bayesian_ridge_regressor import BayesianRidgeRegressorStep
from src.task.step.steps.bh_adjust import BhAdjustStep
from src.task.step.steps.elastic_net_regressor import ElasticNetRegressorStep
from src.task.step.steps.factor_analysis import FactorAnalysisStep
from src.task.step.steps.huber_regressor import HuberRegressorStep
from src.task.step.steps.isomap import IsomapStep
from src.task.step.steps.kernel_pca import KernelPcaStep
from src.task.step.steps.linear_regression import LinearRegressionStep
from src.task.step.steps.mann_whitney import MannWhitneyStep
from src.task.step.steps.mds import MdsStep
from src.task.step.steps.theil_sen_regressor import TheilSenRegressorStep
from src.task.step.steps.truncated_svd import TruncatedSvdStep


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


def _ml_forms(n=30, p=6):
    rng = np.random.default_rng(7)
    data = rng.uniform(0.2, 4.0, size=(n, p)).astype(np.float32)
    features = _form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {f"f{i}": i for i in range(p)}},
    )
    y = rng.normal(size=n).astype(np.float32)
    labels = _form(
        y.reshape(-1, 1),
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(n)}, "label": {"y": 0}},
    )
    return features, labels


@pytest.mark.parametrize(
    "step_cls",
    [
        LinearRegressionStep,
        ElasticNetRegressorStep,
        BayesianRidgeRegressorStep,
        HuberRegressorStep,
        TheilSenRegressorStep,
    ],
)
def test_more_regressor_operators_run(step_cls):
    features, labels = _ml_forms()
    out, export = _run(step_cls(), {"target_label": "y", "test_size": 0.25, "cv_folds": 3}, [features, labels])
    assert out.data.ndim == 2
    assert np.isfinite(export["test_r2"])
    assert np.isfinite(out.data).all()


def _matrix_forms(n=12, p=5):
    rng = np.random.default_rng(11)
    data = rng.uniform(0.5, 3.0, size=(p, n)).astype(np.float32)
    features = _form(
        data,
        ["feature", "sample"],
        {"feature": {f"f{i}": i for i in range(p)}, "sample": {f"s{i}": i for i in range(n)}},
    )
    return features


@pytest.mark.parametrize(
    "step,params",
    [
        (KernelPcaStep(), {"n_components": 2, "kernel": "rbf"}),
        (TruncatedSvdStep(), {"n_components": 2}),
        (FactorAnalysisStep(), {"n_components": 2, "max_iter": 100}),
        (MdsStep(), {"n_components": 2}),
        (IsomapStep(), {"n_components": 2, "n_neighbors": 5}),
    ],
)
def test_more_projection_operators_run(step, params):
    out, export = _run(step, params, [_matrix_forms()])
    assert out.data.shape[0] == 12
    assert out.dims[0] == "sample"
    assert np.isfinite(out.data).all()
    assert export["n_samples"] == 12


def test_bh_adjust_and_mann_whitney():
    pvalues = _form(
        [[0.01], [0.03], [0.04], [0.2]],
        ["feature", "pvalue"],
        {"feature": {"a": 0, "b": 1, "c": 2, "d": 3}, "pvalue": {"P": 0}},
    )
    out, export = _run(BhAdjustStep(), {}, [pvalues])
    assert out.data.shape == (4, 1)
    assert np.allclose(out.data[:, 0], [0.04, 0.0533333, 0.0533333, 0.2], rtol=1e-4, atol=1e-6)
    assert export["n_tests"] == 4

    features = _form(
        [[1.0, 2.0, 10.0, 11.0], [5.0, 6.0, 1.0, 2.0], [3.0, 4.0, 7.0, 8.0]],
        ["feature", "sample"],
        {"feature": {"f0": 0, "f1": 1, "f2": 2},
         "sample": {"a": 0, "b": 1, "c": 2, "d": 3}},
    )
    meta = _form(
        [[0], [0], [1], [1]],
        ["sample", "feature"],
        {"sample": {"a": 0, "b": 1, "c": 2, "d": 3}, "feature": {"group": 0}},
        dtype=object,
    )
    out, export = _run(MannWhitneyStep(), {"group_label": "group"}, [features, meta])
    assert out.data.shape == (3, 2)
    assert list(out.labels["statistic"]) == ["U", "P"]
    assert np.isfinite(out.data).all()
    assert export["groups"] == ["0", "1"] or export["groups"] == [0, 1]


def test_more_readers(tmp_path):
    fastq = tmp_path / "reads.fastq"
    fastq.write_text("@r1\nACGT\n+\nIIII\n@r2\nTGCA\n+\nJJJJ\n", encoding="utf-8")
    fq = FastqReader().read(fastq, ["read", "field"], {})
    assert fq.data.shape == (2, 4)
    assert list(fq.labels["field"]) == ["id", "sequence", "quality", "length"]

    h5 = tmp_path / "matrix.hdf5"
    with h5py.File(h5, "w") as fh:
        fh.create_dataset("/expr", data=np.arange(6, dtype=np.float32).reshape(3, 2))
    h = H5Reader().read(h5, ["sample", "feature"], {})
    assert h.data.shape == (3, 2)
    assert h.info["dataset"] == "/expr"

    map_path = tmp_path / "variants.map"
    map_path.write_text("1 rs1 0 100\n1 rs2 0 200\n2 rs3 1 300\n", encoding="utf-8")
    m = MapReader().read(map_path, ["variant", "field"], {})
    assert m.data.shape == (3, 3)
    assert list(m.labels["variant"]) == ["rs1", "rs2", "rs3"]
    assert list(m.labels["field"]) == ["chrom", "cm", "bp"]

    phy = tmp_path / "tree.phy"
    phy.write_text("3 4\nA ACGT\nB ACGT\nC AC-T\n", encoding="utf-8")
    p = PhylipReader().read(phy, ["sequence", "position"], {})
    assert p.data.shape == (3, 4)
    assert list(p.labels["sequence"]) == ["A", "B", "C"]

    nwk = tmp_path / "tree.nwk"
    nwk.write_text("(A:1,B:2)C;", encoding="utf-8")
    n = NewickReader().read(nwk, ["node", "field"], {})
    assert n.data.shape == (3, 4)
    assert set(n.labels["node"]) == {"A", "B", "C"}
    assert list(n.labels["field"]) == ["parent", "branch_length", "depth", "is_leaf"]

    sto = tmp_path / "aln.sto"
    sto.write_text("# STOCKHOLM 1.0\nA ACGT\nB AC-T\n//\n", encoding="utf-8")
    s = StockholmReader().read(sto, ["sequence", "position"], {})
    assert s.data.shape == (2, 4)
    assert list(s.labels["sequence"]) == ["A", "B"]
