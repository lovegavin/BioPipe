"""Tests for the sequence liability scan operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_liability_scan import liability_rows


def _sequence_form(sequences):
    return encode_sequences(sequences, "sequence", "position", "protein")


def _params(**overrides):
    params = {
        "sequence_dim": "sequence",
        "position_dim": "position",
        "include_oxidation": True,
        "context": 3,
        "output": "liabilities",
    }
    params.update(overrides)
    return params


def test_liability_rows_hand_case():
    rows = liability_rows("MNGTQ")
    assert [(row["position"], row["kind"]) for row in rows] == [
        (1, "n_glycosylation"),
        (1, "oxidation"),
        (2, "deamidation"),
    ]
    assert rows[0]["severity"] == "medium"
    assert rows[0]["motif"] == "N[^P][ST]"
    assert rows[0]["context"] == "MNGT"
    assert rows[1]["severity_code"] == 2.0
    assert rows[2]["severity"] == "high"
    assert rows[2]["motif"] == "NG"
    assert rows[2]["context"] == "MNGTQ"


def test_liability_rows_isomerisation_and_pyroglutamate():
    rows = liability_rows("QDNGT")
    assert [(row["position"], row["kind"], row["severity"]) for row in rows] == [
        (1, "pyroglutamate", "low"),
        (2, "isomerization", "high"),
        (3, "deamidation", "high"),
        (3, "n_glycosylation", "medium"),
    ]
    assert [row["severity_code"] for row in rows] == [1.0, 3.0, 3.0, 2.0]


def test_liability_rows_toggle_and_duplicates():
    assert [row["kind"] for row in liability_rows("MM")] == ["oxidation", "oxidation"]
    without = liability_rows("MNGTQ", include_oxidation=False)
    assert [row["kind"] for row in without] == ["n_glycosylation", "deamidation"]
    assert [row["position"] for row in without] == [1, 2]


def test_liability_rows_clean_sequence():
    assert liability_rows("AAAAAA") == []
    with pytest.raises(StepError, match="sequence is empty"):
        liability_rows("")


def test_run_writes_liability_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    ctx["sequences"] = _sequence_form(["MNGT"])
    run(ctx, [
        {
            "name": "sequence_liability_scan",
            "inputs": ["sequences"],
            "params": dict(ctx.step_params),
        }
    ])
    output = ctx["liabilities"]
    assert list(output.dims) == ["liability", "statistic"]
    assert output.data.shape == (3, 3)
    assert "1:oxidation" in output.labels["liability"]
    assert "2:deamidation" in output.labels["liability"]
    assert "1:n_glycosylation" in output.labels["liability"]
    assert output.info["n_liabilities"] == 3
    assert output.info["kinds"] == {"n_glycosylation": 1, "deamidation": 1, "oxidation": 1}
    assert output.info["sequence"] == "MNGT"


def test_run_rejects_multiple_sequences(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    ctx["sequences"] = _sequence_form(["MNGT", "QDNGT"])
    with pytest.raises(StepError, match="expected exactly one sequence"):
        run(ctx, [
            {
                "name": "sequence_liability_scan",
                "inputs": ["sequences"],
                "params": dict(ctx.step_params),
            }
        ])

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(context=50)
    ctx["sequences"] = _sequence_form(["MNGT"])
    with pytest.raises((StepError, ValueError), match="context|maximum"):
        run(ctx, [
            {
                "name": "sequence_liability_scan",
                "inputs": ["sequences"],
                "params": dict(ctx.step_params),
            }
        ])
