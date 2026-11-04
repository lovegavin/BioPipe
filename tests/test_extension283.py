"""sequence_net_charge: net charge and sliding charge."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_net_charge import residue_charges, sliding_charge


def test_charge_hand_cases():
    assert residue_charges("KRDE").sum() == pytest.approx(0.0)
    assert residue_charges("KKK").sum() == pytest.approx(3.0)
    assert list(residue_charges("KR")) == [1.0, 1.0]
    assert sliding_charge(np.array([1.0, 1.0, -1.0]), 2) == pytest.approx([2.0, 0.0])


def test_run_writes_row():
    form = encode_sequences(["KRDE"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp283", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_net_charge", "inputs": ["sequence"], "params": {"output": "charge", "window": 2}}])
    result = ctx["charge"]
    assert result.data.shape == (1, 4)
    assert result.data[0, 0] == pytest.approx(0.0)
    assert result.info["positive"] == 2


def test_errors():
    with pytest.raises(StepError, match="not an amino acid"):
        residue_charges("Z")
    with pytest.raises(StepError, match="shorter than the window"):
        ctx = Context("/tmp/bp283b", {"params": {}})
        ctx["sequence"] = encode_sequences(["KK"], "sequence", "position", "protein")
        run(ctx, [{"name": "sequence_net_charge", "inputs": ["sequence"], "params": {"output": "charge", "window": 9}}])
