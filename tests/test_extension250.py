"""Tests for the signal peptide detection operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_signal_peptide import (
    SequenceSignalPeptideStep,
    hydropathy,
    net_charge,
    signal_peptide,
)

# 12 residue n-region (11 positive charges), a 12 residue leucine h-region, a
# small alanine at -1 and a QA c-region: cleavage after residue 25.
SIGNAL = "MRRRRRRRRRRR" + "L" * 12 + "AQA"
NO_SIGNAL = "MGSSHHHHHHSSGLVPRGSHMASMTGGQQM"


def test_hydropathy() -> None:
    values = hydropathy("ALV")
    assert values.tolist() == pytest.approx([1.8, 3.8, 4.2])
    with pytest.raises(StepError, match="outside the Kyte-Doolittle scale"):
        hydropathy("AXL")
    with pytest.raises(StepError, match="the sequence is empty"):
        signal_peptide("")


def test_net_charge() -> None:
    assert net_charge("") == 0
    assert net_charge("KRD") == 1
    assert net_charge("DEE") == -3
    assert net_charge("MKKQR") == 3


def test_signal_peptide_positive() -> None:
    result = signal_peptide(SIGNAL)
    assert result["detected"] is True
    assert result["cleavage_site"] == 25
    assert result["h_start"] == 10
    assert result["h_end"] == 24
    assert result["h_mean"] == pytest.approx(2.14, abs=1e-2)
    assert result["n_charge"] == 8
    assert SIGNAL[result["cleavage_site"] - 1] in "AGSTCPV"
    assert result["score"] > result["h_mean"]


def test_signal_peptide_negative() -> None:
    result = signal_peptide(NO_SIGNAL)
    assert result["detected"] is False
    assert result["cleavage_site"] == 0
    assert np.isnan(result["h_mean"])


def test_signal_peptide_requires_positive_n() -> None:
    negative = "MDDDDDDDDDDD" + "L" * 12 + "AQA"
    assert signal_peptide(negative)["detected"] is False
    relaxed = signal_peptide(negative, require_positive_n=False)
    assert relaxed["detected"] is True


def test_run(tmp_path) -> None:
    form = encode_sequences([SIGNAL, NO_SIGNAL], "sequence", "position", "protein")
    params = {"output": "signal", "max_length": 40}
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    run(ctx, [{"name": "sequence_signal_peptide", "inputs": ["sequences"], "params": params}])
    out = ctx["signal"]
    assert out.dims == ["peptide", "statistic"]
    assert out.data.shape == (2, 7)
    assert out.info["n_detected"] == 1
    assert out.info["cleavage_sites"][0] == 25
    assert out.info["cleavage_sites"][1] == 0


def test_errors(tmp_path) -> None:
    form = encode_sequences([SIGNAL], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    with pytest.raises(ValueError):
        run(
            ctx,
            [
                {
                    "name": "sequence_signal_peptide",
                    "inputs": ["sequences"],
                    "params": {"output": "signal", "max_length": 5},
                }
            ],
        )
    with pytest.raises(ValueError):
        run(
            ctx,
            [
                {
                    "name": "sequence_signal_peptide",
                    "inputs": ["sequences"],
                    "params": {"output": "signal", "min_hydrophobicity": 9.0},
                }
            ],
        )
    assert SequenceSignalPeptideStep.definition["inputs_arity"] == 1
