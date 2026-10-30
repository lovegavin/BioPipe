from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.bam_reader import BamReader
from src.reader.readers.bigwig_reader import BigWigReader
from src.reader.readers.gfa_reader import GfaReader
from src.reader.readers.ped_reader import PedReader
from src.task.step.steps.distance_correlation import DistanceCorrelationStep
from src.task.step.steps.partial_correlation import PartialCorrelationStep
from src.task.step.steps.power_transform import PowerTransformStep
from src.task.step.steps.quantile_transform import QuantileTransformStep
from src.task.step.steps.rank_transform import RankTransformStep
from src.task.step.steps.robust_scale import RobustScaleStep
from src.task.step.steps.vif import VifStep
from src.task.step.steps.winsorize import WinsorizeStep


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


def _matrix(n=20, p=4, positive=False):
    rng = np.random.default_rng(41)
    data = rng.uniform(0.2, 3.0, size=(n, p)) if positive else rng.normal(size=(n, p))
    return _form(data, ["sample", "feature"], {
        "sample": {f"s{i}": i for i in range(n)},
        "feature": {f"f{i}": i for i in range(p)},
    })


def test_distance_correlation_identical_is_one():
    x = _matrix(20, 4)
    out, export = _run(DistanceCorrelationStep(), {}, [x, x])
    assert out.data.shape == (4, 4)
    assert np.allclose(np.diag(out.data), 1.0, atol=1e-5)
    assert export["n_samples"] == 20


def test_partial_correlation_and_vif():
    x = _matrix(30, 3)
    y = _form(
        x.data + np.random.default_rng(42).normal(scale=0.1, size=x.data.shape),
        list(x.dims),
        {name: dict(values) for name, values in x.labels.items()},
    )
    cov = _matrix(30, 2)
    out, export = _run(PartialCorrelationStep(), {}, [x, y, cov])
    assert out.data.shape == (3, 4)
    assert list(out.labels["statistic"]) == ["r", "t", "p", "df"]
    assert np.isfinite(out.data).all()
    assert export["n_covariates"] == 2

    dup = _form(
        np.column_stack([x.data[:, 0], x.data[:, 0], x.data[:, 1]]),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(30)}, "feature": {"a": 0, "b": 1, "c": 2}},
    )
    vif, _ = _run(VifStep(), {}, [dup])
    assert vif.data.shape == (3, 1)
    assert np.isinf(vif.data[0, 0]) or vif.data[0, 0] > 1e6


def test_quantile_power_and_robust_transforms():
    x = _matrix(24, 4)
    q, qe = _run(QuantileTransformStep(), {"n_quantiles": 10}, [x])
    assert q.data.shape == x.data.shape
    assert np.isfinite(q.data).all()
    assert qe["n_quantiles"] == 10

    p, _ = _run(PowerTransformStep(), {"method": "yeo-johnson"}, [x])
    assert p.data.shape == x.data.shape
    assert np.isfinite(p.data).all()

    r, _ = _run(RobustScaleStep(), {"dim": "sample"}, [x])
    assert r.data.shape == x.data.shape


def test_winsorize_and_rank_transform():
    x = _matrix(20, 3)
    w, we = _run(WinsorizeStep(), {"lower": 10, "upper": 90}, [x])
    assert w.data.shape == x.data.shape
    assert we["lower"] == 10

    r, re = _run(RankTransformStep(), {"normal_score": True}, [x])
    assert r.data.shape == x.data.shape
    assert np.isfinite(r.data).all()
    assert re["normal_score"] is True


def test_bam_reader_and_dispatch(tmp_path):
    pysam = pytest.importorskip("pysam")
    path = tmp_path / "reads.bam"
    header = {"HD": {"VN": "1.6"}, "SQ": [{"SN": "chr1", "LN": 1000}]}
    with pysam.AlignmentFile(str(path), "wb", header=header) as handle:
        record = pysam.AlignedSegment()
        record.query_name = "r1"
        record.query_sequence = "ACGT"
        record.flag = 0
        record.reference_id = 0
        record.reference_start = 10
        record.mapping_quality = 60
        record.cigarstring = "4M"
        record.query_qualities = pysam.qualitystring_to_array("IIII")
        handle.write(record)
    out = BamReader().read(path, ["read", "field"], {})
    assert out.data.shape[0] == 1
    assert "mapping_quality" in out.labels["field"]
    assert pick_reader(path).__class__.__name__ == "BamReader"


def test_bigwig_reader_and_dispatch(tmp_path):
    pyBigWig = pytest.importorskip("pyBigWig")
    path = tmp_path / "track.bw"
    handle = pyBigWig.open(str(path), "w")
    handle.addHeader([("chr1", 1000)])
    handle.addEntries(["chr1"], [0], ends=[100], values=[1.5])
    handle.close()
    out = BigWigReader().read(path, ["region", "field"], {})
    assert out.data.shape == (1, 4)
    assert out.data[0, 3] == pytest.approx(1.5)
    assert pick_reader(path).__class__.__name__ == "BigWigReader"


def test_ped_reader_and_dispatch(tmp_path):
    path = tmp_path / "cohort.ped"
    path.write_text(
        "F1 s1 0 0 1 1 A A A G\n"
        "F1 s2 0 0 2 2 A G G G\n",
        encoding="utf-8",
    )
    out = PedReader().read(path, ["sample", "feature"], {})
    assert out.data.shape == (2, 7)
    assert "gt:1" in out.labels["feature"]
    assert "gt:2" in out.labels["feature"]
    assert pick_reader(path).__class__.__name__ == "PedReader"


def test_gfa_reader_and_dispatch(tmp_path):
    path = tmp_path / "graph.gfa"
    path.write_text("S\tseg1\tACGT\tLN:i:4\nS\tseg2\t*\tLN:i:10\n", encoding="utf-8")
    out = GfaReader().read(path, ["segment", "field"], {})
    assert out.data.shape == (2, 2)
    assert out.data[0, 0] == 4
    assert out.data[0, 1] == pytest.approx(0.5)
    assert np.isnan(out.data[1, 1])
    assert pick_reader(path).__class__.__name__ == "GfaReader"
