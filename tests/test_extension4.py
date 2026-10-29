from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader.readers.bedpe_reader import BedpeReader
from src.reader.readers.clustal_reader import ClustalReader
from src.reader.readers.cytoband_reader import CytobandReader
from src.reader.readers.nexus_reader import NexusReader
from src.reader.readers.paf_reader import PafReader
from src.reader.readers.sam_reader import SamReader
from src.task.step.steps.bartlett import BartlettStep
from src.task.step.steps.bonferroni import BonferroniStep
from src.task.step.steps.fisher_combined import FisherCombinedStep
from src.task.step.steps.friedman import FriedmanStep
from src.task.step.steps.gaussian_random_projection import GaussianRandomProjectionStep
from src.task.step.steps.locally_linear_embedding import LocallyLinearEmbeddingStep
from src.task.step.steps.normaltest import NormaltestStep
from src.task.step.steps.spectral_embedding import SpectralEmbeddingStep
from src.task.step.steps.topic_lda import TopicLdaStep
from src.task.step.steps.wilcoxon import WilcoxonStep


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


def _matrix(n=24, p=8, positive=False):
    rng = np.random.default_rng(23)
    if positive:
        data = rng.uniform(0.2, 4.0, size=(n, p)).astype(np.float32)
    else:
        data = rng.normal(size=(n, p)).astype(np.float32)
    return _form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {f"f{i}": i for i in range(p)}},
    )


def _grouped_forms(n_groups=3, per_group=4, p=3):
    n = n_groups * per_group
    rng = np.random.default_rng(29)
    data = rng.normal(size=(p, n)).astype(np.float32)
    features = _form(
        data,
        ["feature", "sample"],
        {"feature": {f"g{i}": i for i in range(p)},
         "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        np.array([[i // per_group] for i in range(n)], dtype=object),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        dtype=object,
    )
    return features, meta


@pytest.mark.parametrize(
    "step,params",
    [
        (SpectralEmbeddingStep(), {"n_components": 3}),
        (LocallyLinearEmbeddingStep(), {"n_components": 3, "n_neighbors": 6}),
        (GaussianRandomProjectionStep(), {"n_components": 4}),
    ],
)
def test_projection_operators_run(step, params):
    out, export = _run(step, params, [_matrix()])
    assert out.data.shape[0] == 24
    assert out.dims[0] == "sample"
    assert np.isfinite(out.data).all()
    assert export["n_samples"] == 24


def test_topic_lda_operator_runs():
    out, export = _run(TopicLdaStep(), {"n_components": 3, "max_iter": 10}, [_matrix(positive=True)])
    assert out.data.shape == (24, 3)
    assert np.isfinite(out.data).all()
    assert export["n_components"] == 3


def test_paired_and_multi_group_tests_run():
    features, meta = _grouped_forms(n_groups=2, per_group=4, p=2)
    out, export = _run(WilcoxonStep(), {"group_label": "group"}, [features, meta])
    assert out.data.shape == (2, 2)
    assert out.labels["statistic"] == {"W": 0, "P": 1}
    assert export["n_groups"] == 2

    features, meta = _grouped_forms(n_groups=3, per_group=4, p=2)
    for step in (FriedmanStep(), BartlettStep()):
        out, export = _run(step, {"group_label": "group"}, [features, meta])
        assert out.data.shape == (2, 2)
        assert np.isfinite(out.data).all()
        assert export["n_groups"] == 3


def test_normality_and_pvalue_operators_run():
    out, export = _run(NormaltestStep(), {}, [_matrix(n=24, p=3)])
    assert out.data.shape == (3, 2)
    assert out.labels["statistic"] == {"K2": 0, "P": 1}
    assert export["n_features"] == 3

    pvalues = _form(
        [[0.01], [0.04], [0.2]],
        ["feature", "statistic"],
        {"feature": {"a": 0, "b": 1, "c": 2}, "statistic": {"pvalue": 0}},
    )
    out, export = _run(BonferroniStep(), {}, [pvalues])
    assert out.data.shape == (3, 1)
    assert np.allclose(out.data[:, 0], [0.03, 0.12, 0.6])
    assert export["n_tests"] == 3

    two_p = _form(
        [[0.01, 0.02], [0.1, 0.2], [0.5, 0.6]],
        ["feature", "statistic"],
        {"feature": {"a": 0, "b": 1, "c": 2},
         "statistic": {"pvalue1": 0, "pvalue2": 1}},
    )
    out, export = _run(FisherCombinedStep(), {}, [two_p])
    assert out.data.shape == (3, 2)
    assert out.labels["statistic"] == {"chi2": 0, "P": 1}
    assert export["n_pvalues"] == 2


def test_paf_and_sam_readers(tmp_path):
    paf = tmp_path / "hits.paf"
    paf.write_text(
        "q1\t100\t0\t50\t+\tt1\t200\t10\t60\t40\t50\t60\n",
        encoding="utf-8",
    )
    form = PafReader().read(paf, ["region", "field"], {})
    assert form.data.shape == (1, 12)
    assert form.labels["field"]["query_name"] == 0
    assert form.labels["field"]["mapq"] == 11

    sam = tmp_path / "hits.sam"
    sam.write_text(
        "@HD\tVN:1.6\nq1\t0\tt1\t1\t60\t50M\t*\t0\t0\tACGT\tIIII\n",
        encoding="utf-8",
    )
    form = SamReader().read(sam, ["region", "field"], {})
    assert form.data.shape == (1, 11)
    assert form.labels["field"]["cigar"] == 5


def test_bedpe_and_cytoband_readers(tmp_path):
    bedpe = tmp_path / "pairs.bedpe"
    bedpe.write_text("chr1\t10\t20\tchr2\t30\t40\tp1\t5\t+\t-\n", encoding="utf-8")
    form = BedpeReader().read(bedpe, ["region", "field"], {})
    assert form.data.shape == (1, 10)
    assert form.labels["field"]["strand2"] == 9

    cyto = tmp_path / "bands.cytoband"
    cyto.write_text("chr1\t0\t100\tp36.33\tgneg\nchr1\t100\t200\tp36.32\tgpos25\n", encoding="utf-8")
    form = CytobandReader().read(cyto, ["region", "field"], {})
    assert form.data.shape == (2, 5)
    assert form.labels["region"] == {"0": 0, "1": 1}


def test_alignment_readers(tmp_path):
    clustal = tmp_path / "aln.aln"
    clustal.write_text(
        "CLUSTAL W\n\nseq1  ACGT\nseq2  A-GT\n",
        encoding="utf-8",
    )
    form = ClustalReader().read(clustal, ["sequence", "position"], {})
    assert form.data.shape == (2, 4)
    assert np.isnan(form.data[1, 1])
    assert form.labels["sequence"] == {"seq1": 0, "seq2": 1}

    nexus = tmp_path / "aln.nex"
    nexus.write_text(
        "#NEXUS\nBEGIN DATA;\nMATRIX\nseq1 ACGT\nseq2 A-GT\n;\nEND;\n",
        encoding="utf-8",
    )
    form = NexusReader().read(nexus, ["sequence", "position"], {})
    assert form.data.shape == (2, 4)
    assert np.isnan(form.data[1, 1])
