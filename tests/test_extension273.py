"""Tests for the transmembrane topology operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_transmembrane_topology import (
    loop_charge,
    topology_rows,
)

POLY_LEU = "L" * 30


def _sequence_form(sequences):
    return encode_sequences(sequences, "sequence", "position", "protein")


def _params(**overrides):
    params = {
        "sequence_dim": "sequence",
        "position_dim": "position",
        "window": 19,
        "threshold": 1.6,
        "min_length": 12,
        "output": "topology",
    }
    params.update(overrides)
    return params


def test_loop_charge_counts_one_based_inclusive():
    assert loop_charge("KKDDEE", 1, 2) == 2.0
    assert loop_charge("KKDDEE", 3, 6) == -4.0
    assert loop_charge("KKDDEE", 1, 0) == 0.0
    assert loop_charge("KKDDEE", 5, 99) == -2.0


def test_single_segment_positive_inside():
    sequence = "KK" + POLY_LEU + "EE"
    rows, summary = topology_rows(sequence)
    assert len(rows) == 1
    assert (rows[0]["start"], rows[0]["end"], rows[0]["length"]) == (3, 32, 30)
    assert rows[0]["mean_hydropathy"] == pytest.approx(3.8)
    assert rows[0]["side_code"] == 1.0
    assert summary["topology"] == "in"
    assert summary["n_terminal_charge"] == 2.0
    assert summary["loop_charges"] == pytest.approx([2.0])


def test_single_segment_negative_inside():
    sequence = "EE" + POLY_LEU + "KK"
    rows, summary = topology_rows(sequence)
    assert len(rows) == 1
    assert rows[0]["side_code"] == 0.0
    assert summary["topology"] == "out"
    assert summary["n_terminal_charge"] == -2.0


def test_two_segments_alternate_sides():
    sequence = POLY_LEU + "K" * 19 + POLY_LEU
    rows, summary = topology_rows(sequence)
    assert len(rows) == 2
    assert (rows[0]["start"], rows[0]["end"]) == (1, 35)
    assert (rows[1]["start"], rows[1]["end"], rows[1]["length"]) == (50, 79, 30)
    assert [row["side_code"] for row in rows] == [1.0, 0.0]
    assert summary["topology"] == "inout"
    assert summary["loop_charges"] == pytest.approx([0.0, 14.0])


def test_no_hydrophobic_segment_raises():
    with pytest.raises(StepError, match="no transmembrane segment"):
        topology_rows("D" * 40)
    with pytest.raises(StepError, match="no transmembrane segment"):
        topology_rows("L" * 10)


def test_run_writes_topology_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    ctx["sequences"] = _sequence_form(["KK" + POLY_LEU + "EE", "EE" + POLY_LEU + "KK"])
    run(ctx, [
        {
            "name": "sequence_transmembrane_topology",
            "inputs": ["sequences"],
            "params": dict(ctx.step_params),
        }
    ])
    output = ctx["topology"]
    assert list(output.dims) == ["segment", "statistic"]
    assert output.data.shape == (2, 5)
    assert output.labels["segment"]["tm1"] == 0
    assert output.labels["segment"]["tm2"] == 1
    assert output.data[0].tolist() == pytest.approx([3.0, 32.0, 30.0, 3.8, 1.0])
    assert output.data[1].tolist() == pytest.approx([3.0, 32.0, 30.0, 3.8, 0.0])
    assert output.info["n_segments"] == 2
    assert output.info["topology"] == "inout"
    assert output.info["sides"] == ["in", "out"]


def test_run_validation_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    ctx["sequences"] = _sequence_form(["D" * 40])
    with pytest.raises(StepError, match="no transmembrane segment"):
        run(ctx, [
            {
                "name": "sequence_transmembrane_topology",
                "inputs": ["sequences"],
                "params": dict(ctx.step_params),
            }
        ])

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(window=20)
    ctx["sequences"] = _sequence_form(["KK" + POLY_LEU + "EE"])
    with pytest.raises((StepError, ValueError), match="window"):
        run(ctx, [
            {
                "name": "sequence_transmembrane_topology",
                "inputs": ["sequences"],
                "params": dict(ctx.step_params),
            }
        ])
