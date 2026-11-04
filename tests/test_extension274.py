"""sequence_liability_scan: motif liabilities."""

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_liability_scan import liability_rows


def _keys(rows):
    return [(row["position"], row["kind"]) for row in rows]


def _ctx():
    import tempfile

    return Context(tempfile.mkdtemp(), {"params": {}})


def test_liability_rows_hand_case():
    rows = liability_rows("MNGTQ")
    assert _keys(rows) == [(1, "oxidation"), (2, "deamidation"), (2, "n_glycosylation")]
    assert rows[0]["severity"] == "medium"


def test_liability_rows_pyroglutamate():
    rows = liability_rows("QDNGT")
    assert _keys(rows) == [(1, "pyroglutamate"), (3, "deamidation"), (3, "n_glycosylation")]


def test_liability_rows_toggle_and_duplicates():
    assert _keys(liability_rows("MM", include_oxidation=False)) == []
    assert len(liability_rows("MM")) == 2


def test_run_writes_liability_table():
    form = encode_sequences(["MNGT"], "sequence", "position", "protein")
    ctx = _ctx()
    ctx["sequence"] = form
    run(ctx, [{"name": "sequence_liability_scan", "inputs": ["sequence"], "params": {"output": "liabilities"}}])
    result = ctx["liabilities"]
    assert result.data.shape[0] == 3
    assert "1:oxidation" in result.labels["liability"]


def test_errors():
    with pytest.raises(StepError, match="the sequence is empty"):
        liability_rows("")
    form = encode_sequences(["MNGT", "MNGT"], "sequence", "position", "protein")
    ctx = _ctx()
    ctx["sequence"] = form
    with pytest.raises(StepError):
        run(ctx, [{"name": "sequence_liability_scan", "inputs": ["sequence"], "params": {"output": "liabilities"}}])
