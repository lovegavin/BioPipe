"""Tests for the CpG island operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_cpg_island import (
    SequenceCpgIslandStep,
    island_windows,
    merge_windows,
)


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params: dict, form: Form):
    ctx = Ctx(params)
    step = SequenceCpgIslandStep()
    step.run(ctx, [form])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx)


def _cpg_sequence(length: int = 400) -> str:
    # 60 nt CpG-rich island inside an AT-rich background
    island = "CG" * 30
    return "AT" * 100 + island + "TA" * 120


def test_island_windows_hand_math() -> None:
    sequence = "CG" * 50  # 100 nt, GC 1.0, CpG observed 50
    windows = island_windows(sequence, window=50, step=10, gc_min=0.5, cpg_oe_min=0.6)
    assert len(windows) == 6
    start, end, gc, ratio = windows[0]
    assert (start, end) == (0, 50)
    assert gc == 1.0
    assert ratio > 1.0
    assert windows[-1][0] == 50


def test_merge_windows() -> None:
    merged = merge_windows([(0, 50, 0.6, 0.8), (10, 60, 0.7, 0.9), (100, 150, 0.55, 0.7)])
    assert [entry["start"] for entry in merged] == [0, 100]
    assert merged[0]["end"] == 60
    assert merged[0]["windows"] == 2
    assert merged[0]["gc"] == pytest.approx(0.65)
    assert merge_windows([]) == []


def test_step_finds_island_and_labels() -> None:
    sequence = _cpg_sequence()
    form = encode_sequences([sequence], "sequence", "position", "dna")
    out, export = _run({"window": 100, "step": 10, "gc_min": 0.4, "cpg_oe_min": 0.5}, form)
    assert int(out.info["n_islands"]) >= 1
    assert int(out.info["n_sequences"]) == 1
    assert out.dims == ["island", "statistic"]
    assert out.data.shape[1] == 5
    for label, index in out.labels["island"].items():
        assert label.startswith("seq1:")
        start = float(out.data[index, 0])
        end = float(out.data[index, 1])
        assert 1 <= start <= end <= len(sequence)
    assert export["window"] == 100


def test_window_oracle() -> None:
    sequence = ("CGCGCG" + "ATATAT") * 6
    windows = island_windows(sequence, window=30, step=5, gc_min=0.45, cpg_oe_min=0.5)
    manual = []
    for start in range(0, len(sequence) - 30 + 1, 5):
        chunk = sequence[start : start + 30]
        gc = (chunk.count("G") + chunk.count("C")) / 30
        expected = chunk.count("C") * chunk.count("G") / 30
        ratio = chunk.count("CG") / expected if expected else 0.0
        if gc >= 0.45 and ratio >= 0.5:
            manual.append(start)
    assert [entry[0] for entry in windows] == manual
    assert manual


def test_parameter_and_input_errors() -> None:
    form = encode_sequences(["ACGT" * 100], "sequence", "position", "dna")
    for params, match in (
        ({"window": 10}, "window must be an integer between"),
        ({"window": 100, "step": 200}, "step must be a positive integer"),
        ({"gc_min": 2.0}, "gc_min must be in"),
        ({"cpg_oe_min": -1.0}, "cpg_oe_min must not be negative"),
    ):
        with pytest.raises(StepError, match=match):
            _run(params, form)
    with pytest.raises(StepError, match="sequence input expected"):
        _run({}, Form(data=np.zeros((1, 4), dtype=np.float32), dims=["sequence", "feature"], labels={"sequence": {"s": 0}, "feature": {"a": 0, "b": 1, "c": 2, "d": 3}}, info={}))


def test_runner_contract_and_empty_result() -> None:
    from src.task.context.base import Context
    from src.task.runner import run

    form = encode_sequences(["AT" * 200], "sequence", "position", "dna")
    context = Context(__import__("pathlib").Path("/tmp/operon_cpg_runner"), {"params": {}})
    context["data"] = form
    run(
        context,
        [
            {
                "name": "sequence_cpg_island",
                "inputs": ["data"],
                "params": {"output": "islands", "window": 100, "step": 10},
            }
        ],
    )
    out = context["islands"]
    assert int(out.info["n_islands"]) == 0
    assert out.data.shape == (0, 5)
