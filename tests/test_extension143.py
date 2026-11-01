"""Tests for the antibody CDR hydrophobicity operator."""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.antibody_cdr_hydrophobicity import (
    AntibodyCdrHydrophobicityStep,
    cdr_hydrophobicity_row,
    hydrophobic_moment,
)
from src.task.step.steps._sequence_common import encode_sequences

VHH_1MEL = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYADSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
)
CDR1 = "PYCMG"
CDR2 = "AINMGGGITYYADSVKG"
CDR3 = "DSTIYASYYECGHGLSTGGYGYDS"


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "cdr_hydrophobicity", **params}
        self.metadata = {}


def test_moment_uses_100_degree_angle() -> None:
    value = hydrophobic_moment("AC", 2)
    expected = math.hypot(1.8 + 2.5 * math.cos(math.radians(100)), 2.5 * math.sin(math.radians(100))) / 2
    assert value == pytest.approx(expected, abs=1e-9)


def test_row_hand_computation() -> None:
    row = cdr_hydrophobicity_row("PYCMG", window=5)
    assert row["length"] == 5.0
    assert row["hydrophobic_fraction"] == pytest.approx(2.0 / 5.0)
    assert row["max_run"] == 1.0
    assert row["max_moment"] >= 0.0
    empty = cdr_hydrophobicity_row("", window=5)
    assert all(math.isnan(value) for value in empty.values())


def test_step_matches_1mel_fixture() -> None:
    form = encode_sequences([VHH_1MEL], "sequence", "position", "protein")
    output, exported = _run_form(form)
    assert output.data.shape == (3, 5)
    assert list(output.labels["region"]) == ["CDR1", "CDR2", "CDR3"]
    assert output.data[:, 0].tolist() == [5.0, 17.0, 24.0]
    assert output.info["region_sequences"] == {"CDR1": CDR1, "CDR2": CDR2, "CDR3": CDR3}
    for index, text in enumerate((CDR1, CDR2, CDR3)):
        expected = cdr_hydrophobicity_row(text, window=7)
        assert output.data[index, 1] == pytest.approx(expected["hydrophobic_fraction"], abs=1e-6)
        assert output.data[index, 3] == pytest.approx(expected["max_moment"], abs=1e-6)
    assert exported["lengths"] == {"CDR1": 5, "CDR2": 17, "CDR3": 24}


def _run_form(form):
    ctx = _Ctx({})
    step = AntibodyCdrHydrophobicityStep()
    step.run(ctx, [form])
    return ctx["cdr_hydrophobicity"], step.export(ctx)


def test_net_charge_matches_biopython() -> None:
    pytest.importorskip("Bio.SeqUtils.ProtParam")
    from Bio.SeqUtils.ProtParam import ProteinAnalysis

    form = encode_sequences([VHH_1MEL], "sequence", "position", "protein")
    output, _ = _run_form(form)
    for index, text in enumerate((CDR1, CDR2, CDR3)):
        reference = ProteinAnalysis(text).charge_at_pH(7.4)
        assert output.data[index, 4] == pytest.approx(reference, abs=0.5)


def test_custom_regions_and_window() -> None:
    output = _run_form_with({"regions": "CDR3", "window": 5})
    assert output.data.shape == (1, 5)
    assert list(output.labels["region"]) == ["CDR3"]


def _run_form_with(params):
    form = encode_sequences([VHH_1MEL], "sequence", "position", "protein")
    ctx = _Ctx(params)
    step = AntibodyCdrHydrophobicityStep()
    step.run(ctx, [form])
    return ctx["cdr_hydrophobicity"]


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="window must be"):
        _run_form_with({"window": 2})
    with pytest.raises(StepError, match="regions must name"):
        _run_form_with({"regions": " "})
    with pytest.raises(StepError, match="regions must be CDR1, CDR2 or CDR3"):
        _run_form_with({"regions": "CDR4"})
    with pytest.raises(StepError, match="ph must be"):
        _run_form_with({"ph": 15.0})


def test_multi_sequence_and_dims_are_rejected() -> None:
    two = encode_sequences([VHH_1MEL, VHH_1MEL], "sequence", "position", "protein")
    ctx = _Ctx({})
    step = AntibodyCdrHydrophobicityStep()
    with pytest.raises(StepError, match="exactly one sequence"):
        step.run(ctx, [two])
    from src.core.forms.form import Form

    broken = Form(
        data=np.zeros((1, 4), dtype=np.float32),
        dims=["sequence", "value"],
        labels={"sequence": {"a": 0}, "value": {"x": 0, "y": 1, "z": 2, "w": 3}},
    )
    with pytest.raises(StepError, match="dims \\[sequence, position\\]"):
        step.run(ctx, [broken])
