"""Tests for the codon adaptation index operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_codon_adaptation import (
    SequenceCodonAdaptationStep,
    adaptation_index,
    codon_weights,
)

REFERENCE = ["CTGCTGCTGCTA"]


def _form(sequences: list[str]):
    return encode_sequences(sequences, "sequence", "position", "dna")


def test_codon_weights_hand_counted() -> None:
    weights = codon_weights(REFERENCE)
    assert weights["CTG"] == pytest.approx(1.0)
    assert weights["CTA"] == pytest.approx(1.0 / 3.0)
    # Leucine codons absent from the reference get the 0.5 pseudo-count.
    assert weights["TTA"] == pytest.approx(0.5 / 3.0)
    assert weights["ATG"] == pytest.approx(1.0)
    assert codon_weights(REFERENCE, 1.0)["TTA"] == pytest.approx(1.0 / 3.0)


def test_adaptation_index_hand_counted() -> None:
    weights = codon_weights(REFERENCE)
    cai, counted, excluded, optimal = adaptation_index("CTGCTA", weights)
    assert counted == 2 and excluded == 0
    assert cai == pytest.approx((1.0 / 3.0) ** 0.5)
    assert optimal == pytest.approx(0.5)
    assert adaptation_index("ATGCTG", weights)[:3] == pytest.approx((1.0, 1, 1))
    with pytest.raises(StepError, match="no codon left"):
        adaptation_index("ATGTGG", weights)
    with pytest.raises(StepError, match="not part of the standard genetic code"):
        adaptation_index("CTGNNN", weights)


def test_adaptation_index_matches_biopython() -> None:
    CodonAdaptationIndex = pytest.importorskip("Bio.SeqUtils").CodonAdaptationIndex
    oracle = CodonAdaptationIndex(REFERENCE)
    weights = codon_weights(REFERENCE)
    for target in ("CTGCTA", "ATGCTG", "TAA", "CTGTTA", "CTGCTACTG"):
        assert adaptation_index(target, weights)[0] == pytest.approx(
            oracle.calculate(target), rel=1e-12
        )


def test_validation_errors() -> None:
    step = SequenceCodonAdaptationStep()
    assert step.definition["inputs_arity"] == 2
    from src.task.step.steps.sequence_codon_adaptation import _validated

    with pytest.raises(StepError, match="contains non-ACGT characters"):
        _validated(["ACGN"], "target")
    with pytest.raises(StepError, match="not a multiple of three"):
        _validated(["ACGT"], "reference")
    with pytest.raises(StepError, match="is empty"):
        _validated([""], "target")


def test_runner_round_trip(tmp_path) -> None:
    ctx = Context(str(tmp_path / "codon"), {"params": {}})
    ctx["target"] = _form(["CTGCTA"])
    ctx["reference"] = _form(["CTGCTGCTGCTA"])
    run(
        ctx,
        [
            {
                "name": "sequence_codon_adaptation",
                "inputs": ["target", "reference"],
                "params": {"output": "cai"},
            }
        ],
    )
    form = ctx["cai"]
    assert form.dims == ["sequence", "statistic"]
    assert form.data.shape == (1, 4)
    assert np.allclose(
        form.data[0],
        [np.sqrt(1.0 / 3.0), 2.0, 0.0, 0.5],
        rtol=1e-5,
        atol=1e-6,
    )
    assert form.info["absent_weight"] == pytest.approx(0.5)
    assert form.info["n_codons_reference"] == 4
    exports = sorted((tmp_path / "codon").rglob("*sequence_codon_adaptation*.json"))
    assert len(exports) == 1
