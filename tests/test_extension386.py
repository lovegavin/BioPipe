"""Hi-C pair QC and contact binning tests (extension 386)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.step.steps.hic_contact_matrix import HicContactMatrixStep
from src.task.step.steps.hic_distance_decay import HicDistanceDecayStep
from src.task.step.steps.hic_pair_stats import HicPairStatsStep

_PAIRS = """chr1\t100\t0\tchr1\t500\t16
chr1\t1200\t0\tchr1\t1800\t16
chr1\t2200\t0\tchr1\t3500\t16
chr1\t100\t0\tchr2\t400\t16
"""
_SIZES = """chr1\t10000000
chr2\t10000000
"""


class Ctx(dict):
    def __init__(self, params, root=None):
        super().__init__()
        self.step_params = dict(params)
        self._root = Path(root or ".")


def _pairs_artifact(tmp_path):
    path = Path(tmp_path) / "sample.pairs"
    path.write_text(_PAIRS, encoding="utf-8")
    return FileArtifact("pairs", {"pairs": str(path)})


def _sizes_artifact(tmp_path):
    path = Path(tmp_path) / "chrom.sizes.txt"
    path.write_text(_SIZES, encoding="utf-8")
    return FileArtifact("tsv", {"sizes": str(path)})


def _matrix_form(rows):
    names = [f"c{index}" for index in range(len(rows))]
    form = Form(
        np.asarray(rows, dtype=float).reshape(-1, 3),
        dims=["contact", "field"],
        labels={"contact": {name: index for index, name in enumerate(names)},
                "field": {"start1": 0, "start2": 1, "count": 2}},
        info={"chrom": ["chr1"] * len(rows)},
    )
    return form


def _run(cls, ctx, inputs):
    step = cls()
    step.name = step.definition["id"]
    step.run(ctx, inputs)
    return step


def test_pair_statistics_counts(tmp_path):
    ctx = Ctx({"output": "stats"}, tmp_path)
    _run(HicPairStatsStep, ctx, [_pairs_artifact(tmp_path)])
    form = ctx["stats"]
    values = {name: float(form.data[pos, 0]) for name, pos in form.labels["statistic"].items()}
    assert values["total_pairs"] == 4
    assert values["cis_pairs"] == 3
    assert values["trans_pairs"] == 1
    assert values["cis_fraction"] == pytest.approx(0.75)
    assert values["chromosomes"] == 1
    assert form.info["per_chromosome"] == {"chr1": 3}


def test_contact_matrix_bins_cis_pairs(tmp_path):
    ctx = Ctx({"output": "contacts", "resolution": 1000}, tmp_path)
    _run(HicContactMatrixStep, ctx, [_pairs_artifact(tmp_path), _sizes_artifact(tmp_path)])
    form = ctx["contacts"]
    assert form.data.shape == (3, 3)
    rows = {form.labels["contact"][name]: row for name, row in
            zip(form.labels["contact"], form.data)}
    triples = sorted((int(row[0]), int(row[1]), int(row[2])) for row in rows.values())
    assert triples == [(0, 0, 1), (1000, 1000, 1), (2000, 3000, 1)]
    assert form.info["pairs_used"] == 3
    assert form.info["chrom"] == ["chr1", "chr1", "chr1"]


def test_distance_decay_totals(tmp_path):
    rows = [(0, 0, 2), (0, 5000, 3), (0, 20000, 4)]
    form = _matrix_form(rows)
    ctx = Ctx({"output": "decay", "n_bins": 3}, tmp_path)
    _run(HicDistanceDecayStep, ctx, [form])
    out = ctx["decay"]
    assert out.data.shape == (3, 6)
    n_pairs = out.data[:, 3]
    fraction = out.data[:, 5]
    assert int(n_pairs.sum()) == 7
    assert float(fraction.sum()) == pytest.approx(1.0)
    assert out.info["total_pairs"] == 7


def test_distance_decay_rejects_missing_column():
    form = Form(
        np.asarray([[0.0, 1.0]], dtype=float).reshape(-1, 2),
        dims=["contact", "field"],
        labels={"contact": {"a": 0}, "field": {"start1": 0, "count": 1}},
    )
    ctx = Ctx({"output": "decay"})
    with pytest.raises(StepError, match="missing the 'start2' column"):
        _run(HicDistanceDecayStep, ctx, [form])


def test_pair_stats_rejects_empty_file(tmp_path):
    path = Path(tmp_path) / "empty.pairs"
    path.write_text("# empty\n", encoding="utf-8")
    ctx = Ctx({"output": "stats"})
    with pytest.raises(StepError, match="no pairs found"):
        _run(HicPairStatsStep, ctx, [FileArtifact("pairs", {"pairs": str(path)})])


def test_contact_matrix_rejects_missing_sizes(tmp_path):
    empty = Path(tmp_path) / "empty.sizes.txt"
    empty.write_text("", encoding="utf-8")
    ctx = Ctx({"output": "contacts"})
    with pytest.raises(StepError, match="chrom sizes"):
        _run(HicContactMatrixStep, ctx, [_pairs_artifact(tmp_path),
                                        FileArtifact("tsv", {"sizes": str(empty)})])
