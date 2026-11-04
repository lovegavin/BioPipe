"""Tests for the CDR liability motif operator."""

from __future__ import annotations

import re

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_motifs import (
    AntibodyCdrMotifsStep,
    liability_row,
    motif_hits,
    parse_regions,
)

VHH_1MEL = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYADSVKG"
    "RFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDSWGQGTQVTVSS"
    "GRYPYDVPDYGSGRA"
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.written_outputs = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.written_outputs.add(key)


def _form(sequences):
    return encode_sequences(sequences, "sequence", "position", "protein")


def _run(params, sequences=None):
    step = AntibodyCdrMotifsStep()
    ctx = Ctx(params)
    step.run(ctx, [_form(sequences if sequences is not None else [VHH_1MEL])])
    return ctx[params.get("output", "out")], step.export(ctx)


def test_motif_hits_hand_counts() -> None:
    sequence = "AANGSVDPWGGC"
    hits = motif_hits(sequence, 1, len(sequence))
    assert hits["glycosylation"] == [3]
    assert hits["deamidation"] == [3]
    assert hits["isomerization"] == [7]
    assert hits["oxidation"] == [9]
    assert hits["cysteine"] == [12]
    only_c = motif_hits(sequence, 11, 12)
    assert only_c["glycosylation"] == []
    assert only_c["cysteine"] == [12]


def test_liability_row_hand_sum() -> None:
    hits = {
        "glycosylation": [3],
        "deamidation": [3],
        "isomerization": [7],
        "oxidation": [9],
        "cysteine": [12],
    }
    row = liability_row("AANGSVDPWGGC", hits)
    assert row["length"] == 12.0
    assert row["n_glycosylation"] == 1.0
    assert row["n_deamidation"] == 1.0
    assert row["n_isomerization"] == 1.0
    assert row["n_oxidation"] == 1.0
    assert row["n_cysteines"] == 1.0
    assert row["n_liabilities"] == 3.0


def test_step_matches_regex_oracle() -> None:
    out, exported = _run({"output": "liabilities"})
    assert out.dims == ["region", "statistic"]
    assert list(out.labels["region"]) == ["CDR1", "CDR2", "CDR3"]
    assert out.data.shape == (3, 7)
    assert list(out.data[:, 0]) == [5.0, 17.0, 24.0]
    # N-X-S/T with X not proline, NG/NS, DP/DG.
    for name in ("CDR1", "CDR2", "CDR3"):
        residues = out.info["region_sequences"][name]
        assert out.info["motif_positions"][name]["glycosylation"] == [
            match.start() + 1 for match in re.finditer(r"(?=(N[^P][ST]))", residues)
        ]
    assert out.info["region_sequences"]["CDR1"] == "PYCMG"
    assert out.info["region_sequences"]["CDR2"] == "AINMGGGITYYADSVKG"
    assert out.info["region_sequences"]["CDR3"] == "DSTIYASYYECGHGLSTGGYGYDS"
    assert out.info["motif_positions"]["CDR2"]["oxidation"]  # the methionine
    assert exported["regions"] == ["CDR1", "CDR2", "CDR3"]
    assert out.info["numbering_scheme"] == "kabat"


def test_custom_regions_and_parse() -> None:
    out, _ = _run({"regions": "CDR3", "region_dim": "cdr"})
    assert out.dims == ["cdr", "statistic"]
    assert list(out.labels["cdr"]) == ["CDR3"]
    assert out.data.shape == (1, 7)
    assert parse_regions("cdr1, CDR2") == ["CDR1", "CDR2"]


def _run_form(params, form):
    step = AntibodyCdrMotifsStep()
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"]


def test_errors() -> None:
    with pytest.raises(StepError, match="regions must name at least one CDR"):
        parse_regions(" , ")
    with pytest.raises(StepError, match="regions must be CDR1, CDR2 or CDR3"):
        parse_regions("CDR1,CDR4")
    with pytest.raises(StepError, match="regions must be CDR1"):
        _run({"regions": "FR1"})
    with pytest.raises(StepError, match="too short"):
        _run({}, ["ACDE"])
    with pytest.raises(StepError, match="exactly one sequence"):
        _run({}, [VHH_1MEL, VHH_1MEL])
    form = _form([VHH_1MEL])
    form.dims = ["position", "sequence"]
    with pytest.raises(StepError, match="must have dims"):
        _run_form({}, form)


def test_sequence_form_contract() -> None:
    form = _form([VHH_1MEL])
    assert form.info["representation"] == "sequence_codes"
    assert form.info["alphabet"] == "protein"
    assert form.data.shape[0] == 1
