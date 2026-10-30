from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.bcf_reader import BcfReader
from src.reader.readers.genbank_reader import GenBankReader
from src.reader.readers.pdb_reader import PdbReader
from src.reader.readers.zarr_reader import ZarrReader
from src.task.step.steps.bootstrap_ci import BootstrapCiStep
from src.task.step.steps.mantel import MantelStep
from src.task.step.steps.mutual_information import MutualInformationStep
from src.task.step.steps.pls_regression import PlsRegressionStep
from src.task.step.steps.quantile_regression import QuantileRegressionStep
from src.task.step.steps.silhouette import SilhouetteStep


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


def _features(n=30, p=6):
    rng = np.random.default_rng(123)
    return _form(
        rng.normal(size=(n, p)),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {f"f{i}": i for i in range(p)}},
    )


def _reg_labels(x, noise=0.1):
    rng = np.random.default_rng(7)
    y = x.data[:, 0] * 1.5 - x.data[:, 1] * 0.5 + rng.normal(scale=noise, size=x.data.shape[0])
    return _form(
        y.reshape(-1, 1), ["sample", "label"],
        {"sample": dict(x.labels["sample"]), "label": {"y": 0}},
    )


def _class_labels(x, n_classes=3):
    values = np.arange(x.data.shape[0]) % n_classes
    return _form(
        values.reshape(-1, 1), ["sample", "label"],
        {"sample": dict(x.labels["sample"]), "label": {"group": 0}},
    )


def test_mantel_permutation_and_labels():
    rng = np.random.default_rng(3)
    points = rng.normal(size=(10, 3))
    dist = np.sqrt(((points[:, None, :] - points[None, :, :]) ** 2).sum(axis=2))
    labels = {"sample": {f"s{i}": i for i in range(10)},
              "sample_b": {f"s{i}": i for i in range(10)}}
    a = _form(dist, ["sample", "sample_b"], labels)
    raw = dist * 1.2 + rng.normal(scale=0.01, size=dist.shape)
    bdist = 0.5 * (raw + raw.T)
    b = _form(bdist, ["sample", "sample_b"], labels)
    out, export = _run(MantelStep(), {"n_perm": 99}, [a, b])
    assert out.data.shape == (1, 4)
    assert list(out.labels["statistic"]) == ["r", "p", "z", "n"]
    assert out.data[0, 0] > 0.9
    assert 0.0 <= out.data[0, 1] <= 1.0
    assert export["n_samples"] == 10


def test_pls_and_quantile_regression_exports():
    x = _features(36, 5)
    labels = _reg_labels(x)
    out, export = _run(
        PlsRegressionStep(),
        {"target_label": "y", "n_components": 2, "test_size": 0.25, "cv_folds": 2},
        [x, labels],
    )
    assert out.data.shape == (5, 2)
    assert np.isfinite(out.data).all()
    assert "test_r2" in export

    q, qe = _run(
        QuantileRegressionStep(),
        {"target_label": "y", "quantile": 0.5, "solver": "highs", "test_size": 0.25, "cv_folds": 2},
        [x, labels],
    )
    assert q.data.shape == (5, 2)
    assert np.isfinite(q.data).all()
    assert "test_r2" in qe


def test_bootstrap_ci_and_silhouette():
    x = _features(24, 4)
    out, export = _run(BootstrapCiStep(), {"n_boot": 200, "random_state": 2}, [x])
    assert out.data.shape == (4, 3)
    assert np.isfinite(out.data).all()
    assert np.all(out.data[:, 1] <= out.data[:, 0])
    assert np.all(out.data[:, 0] <= out.data[:, 2])
    assert export["n_boot"] == 200

    labels = _class_labels(x, 3)
    s, se = _run(SilhouetteStep(), {"target_label": "group"}, [x, labels])
    assert s.data.shape == (1, 1)
    assert np.isfinite(s.data[0, 0])
    assert se["n_classes"] == 3


def test_mutual_information_classification_and_regression():
    x = _features(30, 5)
    labels = _class_labels(x, 3)
    out, export = _run(MutualInformationStep(), {"target_label": "group"}, [x, labels])
    assert out.data.shape == (5, 1)
    assert np.isfinite(out.data).all()
    assert export["task"] == "classification"

    reg = _reg_labels(x)
    reg_out, reg_export = _run(
        MutualInformationStep(), {"target_label": "y", "task": "regression"}, [x, reg],
    )
    assert reg_out.data.shape == (5, 1)
    assert np.isfinite(reg_out.data).all()
    assert reg_export["task"] == "regression"


def test_genbank_reader(tmp_path):
    path = tmp_path / "sample.gb"
    path.write_text(
        "LOCUS       TEST0001        12 bp    DNA     linear   PLN 01-JAN-2020\n"
        "FEATURES             Location/Qualifiers\n"
        "     gene            1..4\n"
        "                     /gene=\"abc\"\n"
        "     CDS             complement(5..10)\n"
        "ORIGIN\n"
        "        1 acgtacgtacgt\n"
        "//\n",
        encoding="utf-8",
    )
    reader = GenBankReader()
    form = reader.read(path, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert form.data.shape == (1, 3)
    assert list(form.labels["field"]) == ["length", "gc", "features"]
    assert form.data[0, 0] == 12
    assert form.data[0, 1] == pytest.approx(0.5)
    assert form.data[0, 2] == 2
    assert isinstance(pick_reader(path), GenBankReader)


def test_pdb_reader(tmp_path):
    path = tmp_path / "protein.pdb"
    lines = [
        "ATOM      1  CA  ALA A   1      10.000  20.000  30.000  1.00 20.00           C",
        "ATOM      2  CA  GLY A   2      11.000  21.000  31.000  0.50 30.00           C",
        "END",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reader = PdbReader()
    form = reader.read(path, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    assert form.data.shape == (2, 9)
    assert form.data[0, 0] == 10
    assert form.data[1, 1] == 21
    assert list(form.labels["atom"]) == ["atom:1", "atom:2"]
    assert isinstance(pick_reader(path), PdbReader)


def test_zarr_reader(tmp_path):
    zarr = pytest.importorskip("zarr")
    path = tmp_path / "matrix.zarr"
    zarr.save(str(path), np.arange(12, dtype=np.float64).reshape(3, 4))
    form = ZarrReader().read(path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    assert form.data.shape == (3, 4)
    assert form.data[2, 3] == 11
    assert isinstance(pick_reader(path), ZarrReader)


def test_bcf_reader(tmp_path):
    pysam = pytest.importorskip("pysam")
    path = tmp_path / "variants.bcf"
    header = pysam.VariantHeader()
    header.contigs.add("chr1", length=1000)
    with pysam.VariantFile(str(path), "wb", header=header) as handle:
        rec = handle.new_record(contig="chr1", start=9, stop=10, alleles=("A", "C"), qual=42.0)
        handle.write(rec)
    form = BcfReader().read(path, ["variant", "field"], {"variant": "auto", "field": "builtin"})
    assert form.data.shape == (1, 4)
    assert form.data[0, 0] == 10
    assert form.data[0, 1] == 42
    assert list(form.labels["variant"]) == ["chr1:10:A>C"]
    assert isinstance(pick_reader(path), BcfReader)
