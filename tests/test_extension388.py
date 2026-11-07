"""Contract and hand-calculation tests for the proteomics operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._proteomics_utils import (
    digest_peptides,
    peptide_mass,
    peptide_mz,
)
from src.task.step.steps.peptide_coverage import PeptideCoverageStep
from src.task.step.steps.peptide_mass import PeptideMassStep
from src.task.step.steps.protein_digest import ProteinDigestStep


class _Ctx:
    def __init__(self, **params):
        self.step_params = params
        self.values = {}
        self.artifacts = []

    def __setitem__(self, key, value):
        self.values[key] = value

    def artifact_path(self, name):
        return f"/tmp/{name}"


def _fasta(records):
    names = [name for name, _ in records]
    width = max(len(sequence) for _, sequence in records)
    data = np.zeros((len(records), width), dtype=np.float64)
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels={
            "sequence": {name: index for index, name in enumerate(names)},
            "position": {str(index): index for index in range(width)},
        },
        info={"sequences": [sequence for _, sequence in records]},
    )


def _run(step, ctx, inputs):
    step.name = step.definition["id"]
    step.run(ctx, inputs)


def test_digest_trypsin_basic():
    spans = digest_peptides("MKWVTFISLL", "trypsin", 0)
    assert spans == [(0, 2, 0), (2, 10, 0)]


def test_digest_respects_proline():
    assert digest_peptides("AAKPAA", "trypsin", 0) == [(0, 6, 0)]


def test_digest_missed_cleavages():
    spans = digest_peptides("AAKAAKAA", "trypsin", 1)
    assert spans == [
        (0, 3, 0),
        (0, 6, 1),
        (3, 6, 0),
        (3, 8, 1),
        (6, 8, 0),
    ]


def test_peptide_mass_hand_values():
    mass = peptide_mass("MR")
    assert mass == pytest.approx(305.15216062029, abs=1e-9)
    assert peptide_mz(mass, 2) == pytest.approx((mass + 2 * 1.007276466621) / 2)


def test_peptide_mass_rejects_unknown_residue():
    with pytest.raises(StepError, match="unsupported residue"):
        peptide_mass("MX")


def test_digest_operator_reports_peptides():
    step = ProteinDigestStep()
    ctx = _Ctx(min_length=1, max_length=50, output="out")
    _run(step, ctx, [_fasta([("p1", "MKWVTFISLL"), ("p2", "AAKAA")])])
    form = ctx.values["out"]
    assert form.dims == ["peptide", "field"]
    assert form.info["n_peptides"] == 4
    assert form.info["sequences"][:2] == ["MK", "WVTFISLL"]
    assert form.data.shape == (4, 6)
    # second protein is cleaved after K only, so AAK + AA
    assert form.info["sequences"][2:] == ["AAK", "AA"]


def test_digest_operator_default_min_length_drops_dipeptides():
    step = ProteinDigestStep()
    ctx = _Ctx(output="out")
    _run(step, ctx, [_fasta([("p1", "MKWVTFISLL")])])
    assert ctx.values["out"].info["n_peptides"] == 1


def test_peptide_mass_operator_matches_formula():
    digest = ProteinDigestStep()
    ctx = _Ctx(min_length=1, output="peptides")
    _run(digest, ctx, [_fasta([("p1", "MKWVTFISLL")])])
    mass_step = PeptideMassStep()
    ctx2 = _Ctx(peptide_dim="peptide", charge=1, output="masses")
    _run(mass_step, ctx2, [ctx.values["peptides"]])
    form = ctx2.values["masses"]
    expected = peptide_mass("MK")
    assert form.data[0, 0] == pytest.approx(expected, abs=1e-9)
    assert form.data[0, 1] == pytest.approx(expected + 1.007276466621, abs=1e-9)
    assert form.info["n_peptides"] == 2


def test_coverage_operator_merges_intervals():
    digest = ProteinDigestStep()
    ctx = _Ctx(min_length=1, output="peptides")
    _run(digest, ctx, [_fasta([("p1", "MKWVTFISLL"), ("p2", "AAKAA")])])
    peptides = ctx.values["peptides"]
    # keep only the peptides of p1 so p2 has no coverage
    keep = [label for label, _ in peptides.labels["peptide"].items() if label.startswith("p1")]
    rows = np.array([peptides.data[peptides.labels["peptide"][label]] for label in keep])
    trimmed = Form(
        data=rows,
        dims=peptides.dims,
        labels={
            "peptide": {label: index for index, label in enumerate(keep)},
            "field": dict(peptides.labels["field"]),
        },
        info={"proteins": list(peptides.info["proteins"])},
    )
    step = PeptideCoverageStep()
    ctx2 = _Ctx(output="coverage")
    _run(step, ctx2, [_fasta([("p1", "MKWVTFISLL"), ("p2", "AAKAA")]), trimmed])
    form = ctx2.values["coverage"]
    assert form.data.shape == (2, 4)
    p1 = form.data[form.labels["protein"]["p1"]]
    p2 = form.data[form.labels["protein"]["p2"]]
    assert p1[1] == pytest.approx(10.0)
    assert p1[2] == pytest.approx(1.0)
    assert p2[3] == pytest.approx(0.0)


def test_coverage_rejects_single_peptide():
    step = PeptideCoverageStep()
    ctx = _Ctx(output="coverage")
    table = Form(
        data=np.zeros((1, 3)),
        dims=["peptide", "field"],
        labels={"peptide": {"p1:1-2": 0}, "field": {"protein_index": 0}},
        info={"proteins": ["p1"]},
    )
    with pytest.raises(StepError, match="missing field"):
        _run(step, ctx, [_fasta([("p1", "MK")]), table])
