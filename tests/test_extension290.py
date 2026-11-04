"""sequence_cysteine_pairing: disulfide pairing hypotheses."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_cysteine_pairing import cysteine_positions, pairing_rows


def test_positions_and_pairing():
    assert cysteine_positions("ACCDEFGCCH") == [2, 3, 8, 9]
    rows = pairing_rows([2, 3, 8, 9])
    assert [(r["first"], r["second"]) for r in rows] == [(2, 3), (8, 9)]
    outer = pairing_rows([2, 3, 8, 9], scheme="outer")
    assert [(r["first"], r["second"]) for r in outer] == [(2, 9), (3, 8)]


def test_run_writes_pairs():
    form = encode_sequences(["ACCDEFGCCH"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp290", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_cysteine_pairing", "inputs": ["sequence"], "params": {"output": "pairs"}}])
    result = ctx["pairs"]
    assert result.data.shape == (2, 3)
    assert result.info["n_cysteines"] == 4


def test_errors():
    with pytest.raises(StepError, match="at least two cysteines"):
        pairing_rows([3])
    with pytest.raises(StepError, match="odd number"):
        pairing_rows([2, 3, 7])
    with pytest.raises(StepError, match="unknown scheme"):
        pairing_rows([2, 3], scheme="zigzag")
