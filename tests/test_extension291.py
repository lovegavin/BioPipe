"""sequence_hydrophobic_moment: helical moment arithmetic."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_hydrophobic_moment import hydrophobic_moment


def test_poly_leucine_closed_form():
    mean_moment, mean_h, moments = hydrophobic_moment("L" * 9)
    theta = np.deg2rad(100.0)
    expected = abs(np.sin(4.5 * theta) / np.sin(0.5 * theta)) * 1.06
    assert moments[0] == pytest.approx(expected, rel=1e-9)
    assert mean_h == pytest.approx(1.06)


def test_amphipathic_contrast():
    amphipathic = hydrophobic_moment("LLKKLLKKL")[0]
    uniform = hydrophobic_moment("LLLLLLLLL")[0]
    assert amphipathic > uniform


def test_run_writes_row():
    form = encode_sequences(["LLKKLLKKL"], "sequence", "position", "protein")
    ctx = Context("/tmp/bp291", {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_hydrophobic_moment", "inputs": ["sequence"], "params": {"output": "moment"}}])
    result = ctx["moment"]
    assert result.data.shape == (1, 4)
    assert result.info["n_windows"] == 1


def test_errors():
    with pytest.raises(StepError, match="at least nine residues"):
        hydrophobic_moment("LLLL")
    with pytest.raises(StepError, match="outside the Eisenberg scale"):
        hydrophobic_moment("XXXXXXXXX")
