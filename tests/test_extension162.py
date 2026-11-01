"""Tests for the v1.30.0 prosite_scan operator."""

from __future__ import annotations

import re

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.prosite_scan import (
    PrositeScanStep,
    find_hits,
    parse_patterns,
    translate_pattern,
)


def _form(sequences):
    return encode_sequences(sequences, "sequence", "position", "protein")


def _run(step, params, forms):
    class Ctx(dict):
        def __init__(self, params):
            self.step_params = {"output": "out", **params}
            self.metadata = {}

    ctx = Ctx(params)
    step.run(ctx, list(forms))
    return ctx[params.get("output", "out")]


def test_translate_pattern() -> None:
    assert translate_pattern("N-{P}-[ST]") == "N[^P][ST]"
    assert translate_pattern("C-x-C") == "C.C"
    assert translate_pattern("[AG].x") == "[AG]."
    with pytest.raises(StepError, match="unclosed"):
        translate_pattern("N-[ST")
    with pytest.raises(StepError, match="unexpected"):
        translate_pattern("N]ST")
    with pytest.raises(StepError, match="empty"):
        translate_pattern("")
    with pytest.raises(StepError, match="empty character set"):
        translate_pattern("N-[]ST")
    with pytest.raises(StepError, match="does not select"):
        translate_pattern("--")


def test_find_hits_overlapping() -> None:
    assert find_hits("AANGSV", "N[^P][ST]") == [3]
    assert find_hits("NNN", "NN") == [1, 2]
    assert find_hits("AAAA", "AA") == [1, 2, 3]


def test_step_output() -> None:
    step = PrositeScanStep()
    form = _form(["AANGSV", "GGNNST"])
    out = _run(step, {"patterns": "N-{P}-[ST] N-glycosylation\nG-G di-glycine", "motif_dim": "motif"}, [form])
    assert list(out.dims) == ["motif", "statistic"]
    assert list(out.labels["motif"]) == ["N-glycosylation", "di-glycine"]
    data = np.asarray(out.data)
    assert data.shape == (2, 4)
    assert data[0, 0] == 3.0  # one hit in the first, two in the second sequence
    assert data[0, 1] == 2.0
    assert data[0, 2] == 3.0  # first hit position
    assert data[1, 0] == 1.0  # GG at 1,2 in the second sequence only
    assert out.info["patterns"] == ["N-{P}-[ST]", "G-G"]
    assert out.info["hits"]["N-glycosylation"][0]["positions"] == [3]
    assert out.info["hits"]["N-glycosylation"][1]["positions"] == [3, 4]
    assert step.export(None)["total_hits"] == 4


def test_parse_patterns() -> None:
    assert parse_patterns("N-{P}-[ST] glyco\n\n# note\nC-x-C zinc") == [
        ("N-{P}-[ST]", "glyco"),
        ("C-x-C", "zinc"),
    ]
    with pytest.raises(StepError, match="at least one pattern"):
        parse_patterns("\n# only comments\n")
    with pytest.raises(StepError, match="unique"):
        parse_patterns("A-x-A dup\nC-x-C dup")


def test_errors() -> None:
    step = PrositeScanStep()
    form = _form(["AANGSV"])
    with pytest.raises(StepError, match="sequence input expected"):
        step.run(_Ctx({"patterns": "A-x-A", "sequence_dim": "peptide", "output": "out"}), [form])
    with pytest.raises(StepError, match="at least one pattern"):
        _run(step, {"patterns": ""}, [form])


def _Ctx(params):
    class Ctx(dict):
        def __init__(self, params):
            self.step_params = {"output": "out", **params}
            self.metadata = {}

    return Ctx(params)
