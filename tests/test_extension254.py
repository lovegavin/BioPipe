"""Tests for the VHH humanization score operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.vhh_humanization_score import (
    HUMAN_IGHJ4,
    HUMAN_IGHV3_23,
    VhhHumanizationScoreStep,
    compare_regions,
    humanization_rows,
)

VHH = (
    "DVQLQASGGGSVQAGGSLRLSCAASGYTIGPYCMGWFRQAPGKEREGVAAINMGGGITYYA"
    "DSVKGRFTISQDNAKNTVYLLMNSLEPEDTAIYYCAADSTIYASYYECGHGLSTGGYGYDS"
    "WGQGTQVTVSSGRYPYDVPDYGSGRA"
)


def test_compare_regions() -> None:
    assert compare_regions("EVQL", "EVQL", operator="t") == (4, 0)
    assert compare_regions("EVQL", "EVEL", operator="t") == (4, 1)
    with pytest.raises(StepError, match="empty framework"):
        compare_regions("", "EVQL", operator="t")


def test_humanization_rows() -> None:
    rows = humanization_rows(VHH)
    assert len(rows) == 5
    for compared, mismatches, fraction, identity in rows:
        assert compared > 0
        assert 0 <= mismatches <= compared
        assert fraction == pytest.approx(mismatches / compared)
        assert identity == pytest.approx(1.0 - fraction)
    overall = rows[-1]
    assert overall[0] == sum(row[0] for row in rows[:4])
    assert overall[1] == sum(row[1] for row in rows[:4])
    # A VHH framework is close to, but not identical with, IGHV3-23.
    assert 0.0 <= overall[2] <= 0.6

    # A germline-like framework scores higher than an unrelated one.
    germline = "EVQLLESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKG"
    germline_fr2 = humanization_rows(germline + VHH[-40:])
    assert germline_fr2[0][3] >= rows[0][3]
    assert 0.4 <= overall[3] <= 1.0


def test_run(tmp_path) -> None:
    form = encode_sequences([VHH], "sequence", "position", "protein")
    ctx = Context(tmp_path / "humanization-task", {"params": {}})
    ctx["vhh"] = form
    run(ctx, [{"name": "vhh_humanization_score", "inputs": ["vhh"], "params": {"output": "hum"}}])
    out = ctx["hum"]
    assert out.dims == ["framework", "statistic"]
    assert out.data.shape == (5, 4)
    assert set(out.labels["framework"]) == {"FR1", "FR2", "FR3", "FR4", "overall"}
    assert out.labels["framework"]["overall"] == 4
    assert out.info["reference"]["FR4"] == "IGHJ4*01"


def test_errors(tmp_path) -> None:
    with pytest.raises(StepError, match="empty sequence"):
        humanization_rows("")
    with pytest.raises(StepError, match="too short"):
        humanization_rows("ACDE")
    ctx = Context(tmp_path / "humanization-task2", {"params": {}})
    ctx["vhh"] = encode_sequences([VHH, VHH], "sequence", "position", "protein")
    with pytest.raises(StepError, match="exactly one VHH sequence"):
        run(ctx, [{"name": "vhh_humanization_score", "inputs": ["vhh"], "params": {}}])
    assert HUMAN_IGHV3_23.startswith("EVQLL")
    assert HUMAN_IGHJ4 == "WGQGTLVTVSS"
