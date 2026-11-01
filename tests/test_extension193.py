from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_gc_profile import (
    SequenceGcProfileStep,
    at_skew,
    cpg_observed_expected,
    composition_row,
    gc3,
    gc_content,
    window_contents,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(sequences) -> Form:
    return encode_sequences(sequences, "sequence", "position", "dna")


def test_composition_hand_values() -> None:
    assert gc_content("ACGTACGT") == pytest.approx(0.5)
    assert gc3("ACGTACGT") == pytest.approx(1.0)
    assert cpg_observed_expected("ACGTACGT") == pytest.approx(4.0)
    assert at_skew("ACGTACGT") == pytest.approx(0.0)
    assert gc_content("UUUU") == pytest.approx(0.0)


def test_window_contents() -> None:
    windows = window_contents("ACGTACGT", 4)
    assert len(windows) == 5
    assert windows[0] == {"start": 1, "end": 4, "gc": 0.5}
    assert len(window_contents("ACGT", 5)) == 0


def test_composition_row_std_zero_for_uniform_windows() -> None:
    row, windows = composition_row("ACGTACGT", 4)
    assert row[0] == pytest.approx(0.5)
    assert row[4] == pytest.approx(0.0)


def test_step_output() -> None:
    step = SequenceGcProfileStep()
    ctx = Ctx({})
    step.run(ctx, [_form(["ACGTACGT", "GGCC"])])
    out = ctx["out"]
    assert list(out.dims) == ["sequence", "statistic"]
    assert list(out.labels["sequence"].keys()) == ["1", "2"]
    assert out.data[0].tolist() == pytest.approx([0.5, 1.0, 4.0, 0.0, 0.0])
    assert out.data[1, 0] == pytest.approx(1.0)
    assert out.info["n_sequences"] == 2
    assert step.export(ctx)["mean_gc"] == pytest.approx(0.75)


def test_errors() -> None:
    with pytest.raises(StepError, match="window must be at least 1"):
        SequenceGcProfileStep().run(Ctx({"window": 0}), [_form(["ACGT"])])
    with pytest.raises(StepError, match="not a DNA/RNA base"):
        gc_content("ACGTX")
    form = _form(["ACGT"])
    with pytest.raises(StepError, match="sequence input expected"):
        SequenceGcProfileStep().run(Ctx({"sequence_dim": "other"}), [form])
