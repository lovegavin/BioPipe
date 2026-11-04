"""sequence_transmembrane_topology: TM spans and in/out sides."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_transmembrane_topology import loop_charge, topology_rows


def _ctx():
    import tempfile

    return Context(tempfile.mkdtemp(), {"params": {}})


def test_loop_charge():
    assert loop_charge("KKDDEE", 1, 2) == 2.0
    assert loop_charge("KKDDEE", 3, 6) == -4.0
    assert loop_charge("KKDDEE", 5, 99) == -2.0


def test_single_segment_positive_inside():
    rows, summary = topology_rows("K" * 6 + "L" * 30)
    assert len(rows) == 1
    assert (rows[0]["start"], rows[0]["end"], rows[0]["length"]) == (2, 36, 35)
    assert rows[0]["side_code"] == 1.0
    assert summary["topology"] == "in"


def test_single_segment_negative_inside():
    rows, summary = topology_rows("D" * 6 + "L" * 30)
    assert rows[0]["side_code"] == 0.0
    assert summary["topology"] == "out"


def test_two_segments_alternate_sides():
    rows, summary = topology_rows("L" * 30 + "K" * 19 + "L" * 30)
    assert [(row["start"], row["end"]) for row in rows] == [(1, 35), (45, 79)]
    assert [row["side_code"] for row in rows] == [1.0, 0.0]
    assert summary["topology"] == "inout"
    assert summary["loop_charges"] == pytest.approx([0.0, 9.0])


def test_run_writes_topology_table():
    form = encode_sequences(["K" * 6 + "L" * 30], "sequence", "position", "protein")
    ctx = _ctx()
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_transmembrane_topology", "inputs": ["sequence"], "params": {"output": "topology"}}])
    assert ctx["topology"].info["n_segments"] == 1


def test_errors():
    with pytest.raises(StepError, match="no transmembrane segment"):
        topology_rows("D" * 40)
    form = encode_sequences(["L" * 40, "L" * 40], "sequence", "position", "protein")
    ctx = _ctx()
    ctx["sequence"] = form
    with pytest.raises(StepError):
        run(ctx, [{"name": "sequence_transmembrane_topology", "inputs": ["sequence"], "params": {"output": "topology"}}])
