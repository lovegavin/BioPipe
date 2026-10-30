from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.blast_tabular_reader import BlastTabularReader
from src.reader.readers.bedmethyl_reader import BedMethylReader
from src.reader.readers.embl_reader import EmblReader
from src.reader.readers.hmm_reader import HmmReader
from src.reader.readers.hmmer_tblout_reader import HmmerTbloutReader
from src.reader.readers.interproscan_reader import InterProScanReader
from src.reader.readers.mol2_reader import Mol2Reader
from src.reader.readers.smi_reader import SmiReader
from src.task.step.steps.adjusted_rand import AdjustedRandStep
from src.task.step.steps.by_adjust import ByAdjustStep
from src.task.step.steps.calinski_harabasz import CalinskiHarabaszStep
from src.task.step.steps.cliffs_delta import CliffsDeltaStep
from src.task.step.steps.cohens_d import CohensDStep
from src.task.step.steps.confusion_matrix import ConfusionMatrixStep
from src.task.step.steps.davies_bouldin import DaviesBouldinStep
from src.task.step.steps.eta_squared import EtaSquaredStep
from src.task.step.steps.holm_adjust import HolmAdjustStep
from src.task.step.steps.mann_kendall import MannKendallStep
from src.task.step.steps.rank_biserial import RankBiserialStep
from src.task.step.steps.roc_curve import RocCurveStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _two_group_forms():
    a = np.array([[1.0, 2.0], [2.0, 2.0], [3.0, 2.0]])
    b = np.array([[2.0, 1.0], [4.0, 1.0], [6.0, 1.0]])
    data = np.vstack([a, b]).T
    data_form = _form(
        data, ["feature", "sample"],
        {"feature": {"f0": 0, "f1": 1}, "sample": {f"s{i}": i for i in range(6)}},
    )
    meta_form = _form(
        np.repeat([0, 1], 3).reshape(-1, 1), ["sample", "group"],
        {"sample": {f"s{i}": i for i in range(6)}, "group": {"group": 0}},
    )
    return data_form, meta_form


def test_holm_and_by_adjustment():
    p = [0.01, 0.04, 0.03, 0.005]
    form = _form(
        np.asarray(p).reshape(-1, 1), ["feature", "pvalue"],
        {"feature": {f"g{i}": i for i in range(4)}, "pvalue": {"p": 0}},
    )
    holm, info = _run(HolmAdjustStep(), {}, [form])
    assert info["method"] == "holm"
    assert holm.data[:, 0] == pytest.approx([0.03, 0.06, 0.06, 0.02], abs=1e-6)
    by, _ = _run(ByAdjustStep(), {}, [form])
    assert by.data[:, 0] == pytest.approx([1 / 24, 1 / 12, 1 / 12, 1 / 24], abs=1e-6)


def test_effect_size_operators_hand_values():
    data, meta = _two_group_forms()
    d, _ = _run(CohensDStep(), {"group_label": "group"}, [data, meta])
    assert d.data.shape == (2, 2)
    assert d.data[0, 0] == pytest.approx(-1.264911, abs=1e-5)
    assert d.data[0, 1] == pytest.approx(-1.011929, abs=1e-5)

    cliff, _ = _run(CliffsDeltaStep(), {"group_label": "group"}, [data, meta])
    assert cliff.data[0, 0] == pytest.approx(-2.0 / 3.0, abs=1e-6)

    eta, _ = _run(EtaSquaredStep(), {"group_label": "group"}, [data, meta])
    assert eta.data[0, 0] == pytest.approx(0.375, abs=1e-6)

    rb, _ = _run(RankBiserialStep(), {"group_label": "group"}, [data, meta])
    assert rb.data[0, 0] == pytest.approx(-2.0 / 3.0, abs=1e-6)


def test_cluster_validity_and_agreement_metrics():
    features = _form(
        np.array([[0, 0], [0.1, 0], [10, 10], [10.1, 10]], dtype=float),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(4)}, "feature": {"x": 0, "y": 1}},
    )
    labels = _form(
        np.array([[0], [0], [1], [1]]), ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(4)}, "label": {"cluster": 0}},
    )
    db, de = _run(DaviesBouldinStep(), {"target_label": "cluster"}, [features, labels])
    assert db.data.shape == (3, 1)
    assert de["n_clusters"] == 2
    assert db.data[0, 0] >= 0

    ch, ce = _run(CalinskiHarabaszStep(), {"target_label": "cluster"}, [features, labels])
    assert ch.data[0, 0] > 0
    assert ce["n_clusters"] == 2

    ari_form = _form(
        np.array([[0, 0], [0, 0], [1, 1], [1, 1]]), ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(4)},
         "label": {"truth": 0, "pred": 1}},
    )
    ari, _ = _run(AdjustedRandStep(), {"true_label": "truth", "pred_label": "pred"}, [ari_form])
    assert ari.data[0, 0] == pytest.approx(1.0)


def test_confusion_and_roc_operators():
    cm_form = _form(
        np.array([[0, 0], [0, 1], [1, 1], [1, 0]]), ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(4)},
         "label": {"truth": 0, "pred": 1}},
    )
    cm, info = _run(ConfusionMatrixStep(), {"true_label": "truth", "pred_label": "pred"}, [cm_form])
    assert cm.data.tolist() == [[1, 1], [1, 1]]
    assert info["classes"] == ["0", "1"]

    label_form = _form(
        np.array([[0], [0], [1], [1]]), ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(4)}, "label": {"truth": 0}},
    )
    score_form = _form(
        np.array([[0.1], [0.2], [0.8], [0.9]]), ["sample", "score"],
        {"sample": {f"s{i}": i for i in range(4)}, "score": {"score": 0}},
    )
    roc, rinfo = _run(RocCurveStep(), {"target_label": "truth"}, [label_form, score_form])
    assert roc.data.shape[1] == 3
    assert rinfo["positive_label"] == "1"
    assert roc.data[:, 0].max() == pytest.approx(1.0)
    assert roc.data[:, 1].max() == pytest.approx(1.0)


def test_mann_kendall_hand_monotonic_series():
    x = np.arange(1, 11, dtype=float).reshape(-1, 1)
    form = _form(
        x, ["time", "feature"],
        {"time": {f"t{i}": i for i in range(10)}, "feature": {"x": 0}},
    )
    out, info = _run(MannKendallStep(), {}, [form])
    assert info["n_features"] == 1
    assert out.data[0, 0] == pytest.approx(45.0)
    assert out.data[0, 1] == pytest.approx(1.0)
    assert out.data[0, 3] < 1e-4


def test_blast_and_hmmer_tabular_readers(tmp_path):
    blast = tmp_path / "hits.b6"
    blast.write_text(
        "q1\ts1\t99.0\t100\t1\t0\t1\t100\t5\t104\t1e-30\t200\n"
        "q2\ts2\t80.0\t50\t5\t1\t2\t51\t10\t59\t1e-5\t90\n",
        encoding="utf-8",
    )
    b = BlastTabularReader().read(blast, ["hit", "field"], {"hit": "auto", "field": "builtin"})
    assert b.data.shape == (2, 12)
    assert list(b.labels["field"])[:3] == ["query_id", "subject_id", "identity"]
    assert b.data[0, 10] == pytest.approx(1e-30, rel=1e-5)

    hmmer = tmp_path / "hits.tblout"
    hmmer.write_text(
        "# comment\n"
        "target1 - query1 - 1e-20 100.0 0.1 1e-20 100.0 0.1 1.0 1 1 0 1 1 1 1 1 description here\n",
        encoding="utf-8",
    )
    h = HmmerTbloutReader().read(hmmer, ["hit", "field"], {"hit": "auto", "field": "builtin"})
    assert h.data.shape == (1, 19)
    assert list(h.labels["field"])[-1] == "description"
    assert h.data[0, 4] == pytest.approx(1e-20, rel=1e-5)


def test_more_text_readers(tmp_path):
    ipr = tmp_path / "hits.iprscan"
    ipr.write_text(
        "P1\tmd5\t100\tPfam\tPF1\tdomain\t1\t50\t1e-10\tT\t01-01-2020\tIPR1\tdesc\tGO:1\tpath\n",
        encoding="utf-8",
    )
    i = InterProScanReader().read(ipr, ["match", "field"], {"match": "auto", "field": "builtin"})
    assert i.data.shape == (1, 15)
    assert i.data[0, 2] == 100

    embl = tmp_path / "seq.embl"
    embl.write_text(
        "ID   AB0001; SV 1; linear; genomic DNA; STD; PRO; 8 BP.\n"
        "AC   AB0001;\n"
        "DE   test sequence\n"
        "OS   Test organism\n"
        "FT   gene            1..8\n"
        "SQ   Sequence 8 BP;\n"
        "     atgcgcat\n"
        "//\n",
        encoding="utf-8",
    )
    e = EmblReader().read(embl, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert e.data.shape == (1, 7)
    assert e.data[0, 4] == 8
    assert e.data[0, 5] == pytest.approx(0.5)

    hmm = tmp_path / "model.hmm"
    hmm.write_text(
        "HMMER3/f [3.3.2]\n"
        "NAME  model1\n"
        "LENG  10\n"
        "ALPH  amino\n"
        "NSEQ  3\n"
        "//\n",
        encoding="utf-8",
    )
    hm = HmmReader().read(hmm, ["model", "field"], {"model": "auto", "field": "builtin"})
    assert hm.data.shape == (1, 4)
    assert hm.data[0, 1] == 10


def test_structure_and_smiles_readers(tmp_path):
    mol2 = tmp_path / "mol.mol2"
    mol2.write_text(
        "@<TRIPOS>MOLECULE\n"
        "ligand\n"
        "2 1 0 0 0\n"
        "SMALL\n"
        "USER_CHARGES\n"
        "@<TRIPOS>ATOM\n"
        "1 C1 0.0 0.0 0.0 C.3 1 LIG 0.0\n"
        "@<TRIPOS>BOND\n"
        "1 1 2 1\n",
        encoding="utf-8",
    )
    m = Mol2Reader().read(mol2, ["molecule", "field"], {"molecule": "auto", "field": "builtin"})
    assert m.data.shape == (1, 3)
    assert m.data[0, 1] == 2
    assert m.data[0, 2] == 1

    smi = tmp_path / "mols.smi"
    smi.write_text("CCO ethanol\nc1ccccc1 benzene\n", encoding="utf-8")
    s = SmiReader().read(smi, ["molecule", "field"], {"molecule": "auto", "field": "builtin"})
    assert s.data.shape == (2, 4)
    assert s.data[0, 2] == 3
    assert s.data[1, 3] == 6

    bm = tmp_path / "methyl.bedmethyl"
    bm.write_text(
        "chr1\t0\t100\tm1\t0\t+\t0\t100\t0\t10\t5\t2\t1\t1\t1\n",
        encoding="utf-8",
    )
    b = BedMethylReader().read(bm, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert b.data.shape == (1, 15)
    assert b.data[0, 9] == 10


def test_readers_are_dispatched(tmp_path):
    paths = {
        "hit.b6": BlastTabularReader,
        "hit.tblout": HmmerTbloutReader,
        "hit.iprscan": InterProScanReader,
        "x.embl": EmblReader,
        "x.hmm": HmmReader,
        "x.mol2": Mol2Reader,
        "x.smi": SmiReader,
        "x.bedmethyl": BedMethylReader,
    }
    for name, cls in paths.items():
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert isinstance(pick_reader(path), cls)
