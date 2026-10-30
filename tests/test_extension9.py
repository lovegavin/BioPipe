from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.broadpeak_reader import BroadPeakReader
from src.reader.readers.gff_reader import GffReader
from src.reader.readers.mmcif_reader import MmcifReader
from src.reader.readers.obo_reader import OboReader
from src.reader.readers.sdf_reader import SdfReader
from src.reader.readers.wig_reader import WigReader
from src.task.step.steps.agglomerative import AgglomerativeStep
from src.task.step.steps.classification_metrics import ClassificationMetricsStep
from src.task.step.steps.concordance_index import ConcordanceIndexStep
from src.task.step.steps.cramer_von_mises import CramerVonMisesStep
from src.task.step.steps.dbscan import DbscanStep
from src.task.step.steps.gaussian_mixture import GaussianMixtureStep
from src.task.step.steps.isolation_forest import IsolationForestStep
from src.task.step.steps.tukey_hsd import TukeyHsdStep
from src.task.step.steps.welch_anova import WelchAnovaStep


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


def _features(n=45, p=4):
    rng = np.random.default_rng(11)
    return _form(
        rng.normal(size=(n, p)),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {f"f{i}": i for i in range(p)}},
    )


def test_clustering_operators():
    x = _features()
    db, de = _run(DbscanStep(), {"eps": 1.5, "min_samples": 2}, [x])
    assert db.data.shape == (45, 1)
    assert de["n_samples"] == 45

    ag, ae = _run(AgglomerativeStep(), {"n_clusters": 3}, [x])
    assert ag.data.shape == (45, 1)
    assert ae["n_clusters"] == 3

    gm, ge = _run(GaussianMixtureStep(), {"n_components": 3, "max_iter": 50}, [x])
    assert gm.data.shape == (45, 2)
    assert np.all((gm.data[:, 1] >= 0) & (gm.data[:, 1] <= 1))
    assert "bic" in ge

    iso, ie = _run(IsolationForestStep(), {"n_estimators": 20, "contamination": 0.1}, [x])
    assert iso.data.shape == (45, 2)
    assert set(np.unique(iso.data[:, 1])).issubset({0.0, 1.0})
    assert ie["n_outliers"] >= 0


def test_group_statistics_operators():
    rng = np.random.default_rng(5)
    data = np.hstack([
        rng.normal(0, 1, size=(4, 6)),
        rng.normal(1, 1, size=(4, 6)),
        rng.normal(2, 1, size=(4, 6)),
    ])
    sample_labels = {f"s{i}": i for i in range(18)}
    features = {f"f{i}": i for i in range(4)}
    data_form = _form(data, ["feature", "sample"], {"feature": features, "sample": sample_labels})
    meta_form = _form(
        np.repeat([0, 1, 2], 6).reshape(-1, 1),
        ["sample", "group"],
        {"sample": sample_labels, "group": {"group": 0}},
    )

    two_sample_labels = {f"s{i}": i for i in range(12)}
    two_data = _form(
        data[:, :12], ["feature", "sample"],
        {"feature": features, "sample": two_sample_labels},
    )
    two_meta = _form(
        np.repeat([0, 1], 6).reshape(-1, 1),
        ["sample", "group"],
        {"sample": two_sample_labels, "group": {"group": 0}},
    )
    cm, ce = _run(CramerVonMisesStep(), {"group_label": "group"}, [two_data, two_meta])
    assert cm.data.shape == (4, 2)
    assert ce["n_groups"] == 2

    wa, we = _run(WelchAnovaStep(), {"group_label": "group"}, [data_form, meta_form])
    assert wa.data.shape == (4, 2)
    assert np.isfinite(wa.data).all()
    assert we["n_groups"] == 3

    th, te = _run(TukeyHsdStep(), {"group_label": "group"}, [data_form, meta_form])
    assert th.data.shape == (12, 5)
    assert len(th.labels["comparison"]) == 12
    assert te["n_comparisons"] == 12


def test_concordance_and_classification_metrics():
    n = 12
    times = np.arange(1, n + 1, dtype=float)
    events = np.ones(n)
    risk = -times
    clinical = _form(
        np.column_stack([times, events, risk]),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {"time": 0, "event": 1, "risk": 2}},
    )
    c, ce = _run(
        ConcordanceIndexStep(),
        {"time_label": "time", "event_label": "event", "risk_label": "risk"},
        [clinical],
    )
    assert c.data.shape == (3, 1)
    assert c.data[0, 0] == pytest.approx(1.0)
    assert ce["n_events"] == n

    labels = _form(
        (np.arange(n) >= n // 2).astype(float).reshape(-1, 1),
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(n)}, "label": {"y": 0}},
    )
    scores = _form(
        np.linspace(0, 1, n).reshape(-1, 1),
        ["sample", "score"],
        {"sample": {f"s{i}": i for i in range(n)}, "score": {"score": 0}},
    )
    out, export = _run(
        ClassificationMetricsStep(),
        {"target_label": "y", "score_label": "score"},
        [labels, scores],
    )
    assert out.data.shape == (6, 1)
    assert out.labels["metric"]["ROCAUC"] == 0
    assert out.data[0, 0] == pytest.approx(1.0)
    assert export["positive_label"] == "1"


def test_wig_reader(tmp_path):
    path = tmp_path / "track.wig"
    path.write_text(
        "track type=wiggle_0\n"
        "fixedStep chrom=chr1 start=1 step=1 span=1\n"
        "0.1\n0.2\n"
        "variableStep chrom=chr2 span=2\n"
        "5 0.3\n",
        encoding="utf-8",
    )
    out = WigReader().read(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert out.data.shape == (3, 4)
    assert list(out.labels["field"]) == ["chrom", "start", "end", "value"]
    assert out.data[0, 1] == 0
    assert out.data[2, 1] == 4


def test_broadpeak_and_gff_readers(tmp_path):
    broad = tmp_path / "peaks.broadpeak"
    broad.write_text(
        "chr1\t0\t100\tpeak1\t10\t+\t1.5\t0.01\t0.02\n"
        "chr2\t10\t50\tpeak2\t20\t-\t2.5\t0.03\t0.04\n",
        encoding="utf-8",
    )
    bp = BroadPeakReader().read(broad, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert bp.data.shape == (2, 9)
    assert list(bp.labels["field"])[0] == "chrom"

    gff = tmp_path / "genes.gff2"
    gff.write_text(
        "chr1\tsrc\tgene\t1\t100\t.\t+\t.\tID=g1\n"
        "chr1\tsrc\texon\t10\t50\t1.5\t+\t0\tParent=g1\n",
        encoding="utf-8",
    )
    gf = GffReader().read(gff, ["feature", "field"], {"feature": "auto", "field": "builtin"})
    assert gf.data.shape == (2, 9)
    assert gf.data[0, 3] == 1
    assert gf.data[0, 4] == 100


def test_mmcif_obo_and_sdf_readers(tmp_path):
    cif = tmp_path / "atoms.cif"
    cif.write_text(
        "data_demo\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "ATOM C 1.0 2.0 3.0\n"
        "ATOM O 4.0 5.0 6.0\n"
        "#\n",
        encoding="utf-8",
    )
    atoms = MmcifReader().read(cif, ["atom", "field"], {"atom": "auto", "field": "builtin"})
    assert atoms.data.shape == (2, 5)
    assert atoms.data[0, 2] == pytest.approx(1.0)

    obo = tmp_path / "terms.obo"
    obo.write_text(
        "format-version: 1.2\n\n"
        "[Term]\nid: GO:0001\nname: alpha\nnamespace: biological_process\nis_obsolete: false\n\n"
        "[Term]\nid: GO:0002\nname: beta\nnamespace: molecular_function\nis_obsolete: true\n",
        encoding="utf-8",
    )
    terms = OboReader().read(obo, ["term", "field"], {"term": "auto", "field": "builtin"})
    assert terms.data.shape == (2, 4)
    assert terms.data[0, 3] == 0
    assert terms.data[1, 3] == 1

    sdf = tmp_path / "mol.sdf"
    atom = " " * 31
    sdf.write_text(
        "water\n  demo\ncomment\n"
        "  3  2  0  0  0  0  0  0  0  0999 V2000\n"
        f"{atom}O    0.0 0.0 0.0\n{atom}H    0.0 0.0 1.0\n{atom}H    0.0 1.0 0.0\n"
        "M  END\n$$$$\n",
        encoding="utf-8",
    )
    mol = SdfReader().read(sdf, ["molecule", "field"], {"molecule": "auto", "field": "builtin"})
    assert mol.data.shape == (1, 3)
    assert mol.data[0, 0] == 3
    assert mol.data[0, 2] == pytest.approx(18.015, rel=1e-3)


@pytest.mark.parametrize(
    "suffix, cls",
    [
        (".wig", WigReader),
        (".broadpeak", BroadPeakReader),
        (".gff2", GffReader),
        (".cif", MmcifReader),
        (".obo", OboReader),
        (".sdf", SdfReader),
    ],
)
def test_pick_reader_dispatches_new_formats(tmp_path, suffix, cls):
    path = tmp_path / f"sample{suffix}"
    path.write_text("", encoding="utf-8")
    assert isinstance(pick_reader(path), cls)
