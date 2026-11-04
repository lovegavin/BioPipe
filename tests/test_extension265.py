"""Tests for VHH humanization mutations."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

from src.task.step.steps.antibody_cdr_kabat import TEMPLATE
from src.task.step.steps.vhh_humanization_mutations import humanization_mutations
from src.task.step.steps.vhh_humanization_score import humanization_rows


def test_mutations_humanize_the_frameworks() -> None:
    rows, proposed = humanization_mutations(TEMPLATE)
    assert rows
    assert len(proposed) == len(TEMPLATE)
    for row in rows:
        assert TEMPLATE[row["position"] - 1] == row["donor"]
        assert proposed[row["position"] - 1] == row["reference"]
    scored = humanization_rows(proposed)
    assert scored[-1][1] == 0
    compared, original = humanization_rows(TEMPLATE)[-1][:2]
    assert original == len(rows)
    assert compared > original


def test_reference_sequence_needs_no_mutation() -> None:
    rows, proposed = humanization_mutations(TEMPLATE)
    assert proposed != TEMPLATE
    assert humanization_mutations(proposed)[0] == []


def test_run_round_trip(tmp_path) -> None:
    form = encode_sequences([TEMPLATE], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    ctx.step_params = {"output": "mutations"}
    run(
        ctx,
        [
            {
                "name": "vhh_humanization_mutations",
                "inputs": ["sequence"],
                "params": {"output": "mutations"},
            }
        ],
    )
    out = ctx["mutations"]
    rows, proposed = humanization_mutations(TEMPLATE)
    assert out.data.shape == (len(rows), 4)
    assert out.info["n_mutations"] == len(rows)
    assert out.info["proposed_sequence"] == proposed
    assert out.labels["mutation"] == {f"mut{index + 1}": index for index in range(len(rows))}


def test_run_rejects_humanized_input(tmp_path) -> None:
    _rows, proposed = humanization_mutations(TEMPLATE)
    form = encode_sequences([proposed], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    ctx.step_params = {"output": "mutations"}
    with pytest.raises(StepError, match="already match the human reference"):
        run(
            ctx,
            [
                {
                    "name": "vhh_humanization_mutations",
                    "inputs": ["sequence"],
                    "params": {"output": "mutations"},
                }
            ],
        )


def test_empty_sequence_is_rejected() -> None:
    with pytest.raises(StepError, match="empty sequence"):
        humanization_mutations("  ")
