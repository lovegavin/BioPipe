"""Contract and numeric tests for interval annotation operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.interval_annotate import IntervalAnnotateStep
from src.task.step.steps.interval_coverage import IntervalCoverageStep
from src.task.step.steps.interval_jaccard import IntervalJaccardStep


class Ctx(dict):
    def __init__(self, params, task_dir="."):
        super().__init__()
        self.step_params = dict(params)
        self.task_dir = task_dir

    def artifact_path(self, name):
        raise AssertionError("these operators do not write artifacts")


def _bed(rows, class_field=True):
    chroms = sorted({row[0] for row in rows})
    classes = sorted({row[3] for row in rows}) if class_field else []
    chrom_encoder = LabelEncoder()
    chrom_codes = chrom_encoder.fit_transform(chroms)
    class_encoder = LabelEncoder()
    class_codes = class_encoder.fit_transform(classes) if classes else []
    data = np.zeros((len(rows), 4 if class_field else 3), dtype=float)
    for i, row in enumerate(rows):
        data[i, 0] = chrom_codes[chroms.index(row[0])]
        data[i, 1] = row[1]
        data[i, 2] = row[2]
        if class_field:
            data[i, 3] = class_codes[classes.index(row[3])]
    labels = {
        "region": {},
        "field": {"chrom": 0, "chromStart": 1, "chromEnd": 2},
    }
    encoders = {"field": {"chrom": chrom_encoder}}
    if class_field:
        labels["field"]["name"] = 3
        encoders["field"]["name"] = class_encoder
    return Form(
        data=data,
        dims=["region", "field"],
        labels=labels,
        info={"encoders": encoders},
    )


def _run(step, params, inputs):
    ctx = Ctx({"output": "out", **params})
    step.run(ctx, inputs)
    return ctx["out"]


def test_annotate_priority_and_intergenic():
    features = _bed([("chr1", 100, 200, "promoter"), ("chr1", 150, 250, "exon")])
    intervals = _bed([("chr1", 140, 160, "peak"), ("chr1", 400, 500, "peak")])
    out = _run(
        IntervalAnnotateStep(),
        {"class_names": "promoter,exon", "priority": "promoter,exon"},
        [intervals, features],
    )
    assert out.data.shape == (2, 3)
    assert out.labels["interval"] == {"0": 0, "1": 1}
    assert list(out.data[0]) == [0.0, 2.0, 20.0]
    assert list(out.data[1]) == [2.0, 0.0, 0.0]
    assert out.info["classes"] == ["promoter", "exon"]
    assert out.info["intergenic_index"] == 2

def test_annotate_rejects_unknown_class():
    features = _bed([("chr1", 0, 10, "weird")])
    intervals = _bed([("chr1", 0, 10, "peak")])
    with pytest.raises(StepError, match="unknown classes"):
        _run(IntervalAnnotateStep(), {"class_names": "promoter,exon"}, [intervals, features])


def test_coverage_fraction():
    features = _bed([("chr1", 0, 100, "exon"), ("chr1", 200, 300, "exon")])
    intervals = _bed([("chr1", 50, 250, "peak")])
    out = _run(IntervalCoverageStep(), {"class_names": "promoter,exon"}, [features, intervals])
    row = out.data[1]
    assert list(row) == [2.0, 200.0, 100.0, 0.5, 2.0]
    assert list(out.data[0]) == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_coverage_multiple_classes():
    features = _bed([("chr1", 0, 50, "promoter"), ("chr2", 100, 200, "exon")])
    intervals = _bed([("chr1", 0, 100, "peak"), ("chr2", 150, 250, "peak")])
    out = _run(IntervalCoverageStep(), {"class_names": "promoter,exon"}, [features, intervals])
    assert list(out.data[0]) == [1.0, 50.0, 50.0, 1.0, 1.0]
    assert list(out.data[1]) == [1.0, 100.0, 50.0, 0.5, 1.0]


def test_jaccard_simple():
    a = _bed([("chr1", 0, 100, "a")])
    b = _bed([("chr1", 50, 150, "b")])
    out = _run(IntervalJaccardStep(), {}, [a, b])
    values = dict(zip(out.labels["statistic"], out.data[:, 0]))
    assert values["intersection_bp"] == 50.0
    assert values["union_bp"] == 150.0
    assert values["jaccard"] == pytest.approx(1 / 3)
    assert values["fraction_a_covered"] == pytest.approx(0.5)
    assert values["fraction_b_covered"] == pytest.approx(0.5)


def test_jaccard_disjoint_and_counts():
    a = _bed(
        [
            ("chr1", 0, 10, "a"),
            ("chr1", 20, 30, "a"),
            ("chr1", 100, 110, "a"),
        ]
    )
    b = _bed([("chr1", 5, 25, "b")])
    out = _run(IntervalJaccardStep(), {}, [a, b])
    values = dict(zip(out.labels["statistic"], out.data[:, 0]))
    assert values["n_a"] == 3.0
    assert values["intersection_bp"] == 10.0
    assert values["union_bp"] == 40.0
    assert values["n_a_overlapping"] == 2.0
    assert values["n_b_overlapping"] == 1.0
    assert values["jaccard"] == pytest.approx(10 / 40)

def test_jaccard_disjoint_only():
    a = _bed([("chr1", 0, 10, "a")])
    b = _bed([("chr1", 100, 110, "b")])
    out = _run(IntervalJaccardStep(), {}, [a, b])
    values = dict(zip(out.labels["statistic"], out.data[:, 0]))
    assert values["intersection_bp"] == 0.0
    assert values["jaccard"] == 0.0
    assert values["n_a_overlapping"] == 0.0
