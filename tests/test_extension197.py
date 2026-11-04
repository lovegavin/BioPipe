"""Tests for sequence_kmer_profile and sequence_restriction_sites."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_kmer_profile import (
    SequenceKmerProfileStep,
    entropy,
    kmer_counts,
    kmer_row,
)
from src.task.step.steps.sequence_restriction_sites import (
    ENZYMES,
    SequenceRestrictionSitesStep,
    site_hits,
    site_row,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _dna_form(sequences):
    return encode_sequences(sequences, "sequence", "position", "dna")


def test_kmer_counts_and_entropy() -> None:
    counts = kmer_counts("ACGTACGT", 2)
    assert counts["AC"] == 2 and counts["TA"] == 1 and sum(counts.values()) == 7
    assert entropy(counts, 7) == pytest.approx(1.9502120649, rel=1e-9)


def test_kmer_row_hand_values() -> None:
    row = kmer_row("ACGTACGT", 2)
    assert row["entropy_1"] == pytest.approx(2.0, abs=1e-9)
    assert row["entropy_2"] == pytest.approx(1.9502120649, rel=1e-9)
    assert row["distinct_fraction_k"] == pytest.approx(4 / 7, rel=1e-9)
    assert row["top_kmer_frequency"] == pytest.approx(2 / 7, rel=1e-9)


def test_step_output() -> None:
    form = _dna_form(["ACGTACGT", "AAAA"])
    ctx = Ctx({"output": "out", "k_mer": 2})
    step = SequenceKmerProfileStep()
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (2, 5)
    assert list(out.labels["statistic"]) == [
        "entropy_1", "entropy_2", "entropy_k", "distinct_fraction_k", "top_kmer_frequency"
    ]
    assert out.data[0, 0] == pytest.approx(2.0, abs=1e-5)
    assert out.data[1, 0] == pytest.approx(0.0, abs=1e-6)
    assert out.info["sequences"][1]["top_kmer"] == "AA"
    assert step.export(ctx)["n_sequences"] == 2


def test_kmer_errors() -> None:
    form = _dna_form(["ACGT"])
    step = SequenceKmerProfileStep()
    with pytest.raises(StepError, match="at least 1"):
        step.run(Ctx({"output": "out", "k_mer": 0}), [form])
    with pytest.raises(StepError, match="shorter than k_mer"):
        step.run(Ctx({"output": "out", "k_mer": 5}), [form])
    with pytest.raises(StepError, match="is required"):
        step.run(Ctx({"output": "out", "sequence_dim": "other"}), [form])


def test_restriction_hits_hand_values() -> None:
    hits = site_hits("GAATTCGGATCC")
    assert hits["EcoRI"] == [1]
    assert hits["BamHI"] == [7]
    row = site_row("GAATTCGGATCC")
    assert row["n_sites"] == 2 and row["n_enzymes"] == 2 and row["first_position"] == 1
    assert site_hits("CCCGGG")["SmaI"] == [1]
    assert site_hits("ACGT") == {}


def test_restriction_step_output() -> None:
    form = _dna_form(["GAATTCGGATCC", "ACGT"])
    ctx = Ctx({"output": "out"})
    step = SequenceRestrictionSitesStep()
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (2, 3)
    assert out.data[0].tolist() == [2.0, 2.0, 1.0]
    assert out.data[1].tolist() == [0.0, 0.0, 0.0]
    assert out.info["sequences"][0]["hits"]["EcoRI"] == [1]
    assert step.export(ctx)["n_sites"] == 2
    assert len(ENZYMES) >= 14


def test_restriction_errors() -> None:
    step = SequenceRestrictionSitesStep()
    with pytest.raises(StepError, match="is required"):
        step.run(Ctx({"output": "out", "position_dim": "other"}), [_dna_form(["ACGT"])])
    protein = encode_sequences(["MKV"], "sequence", "position", "protein")
    with pytest.raises(StepError, match="non-nucleotide residues"):
        step.run(Ctx({"output": "out"}), [protein])
