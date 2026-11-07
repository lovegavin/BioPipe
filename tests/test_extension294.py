"""Contract tests for antifold_score."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]



import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import antifold_score as module
from src.task.step.steps.antifold_score import (
    _region_mask,
    parse_posins,
    parse_regions,
    score_dataframe_from_records,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}
        self.artifacts = {}
        self.params = {}
        self.memory = {}


def _record(position="10A", residue="A", chain="A", perplexity=2.0):
    record = {"pdb_posins": position, "pdb_chain": chain, "pdb_res": residue, "perplexity": perplexity}
    for amino in "ACDEFGHIKLMNPQRSTVWY":
        record[amino] = 0.05
    return record


def test_parse_helpers():
    assert parse_regions("cdr1, CDR3") == ("CDR1", "CDR3")
    with pytest.raises(StepError, match="unknown IMGT region"):
        parse_regions("CDR9")
    with pytest.raises(StepError, match="at least one region"):
        parse_regions("")
    assert parse_posins("10A") == 10
    assert parse_posins("108") == 108
    with pytest.raises(StepError, match="cannot read an IMGT position"):
        parse_posins("abc")


def test_region_mask():
    assert _region_mask(27, ("CDR1",)) == 1
    assert _region_mask(26, ("CDR1",)) == 0
    assert _region_mask(110, ("CDR3",)) == 1
    assert _region_mask(40, ("CDR1", "CDR2", "CDR3")) == 0


def test_score_records_hand_case():
    rows = score_dataframe_from_records([_record()], ("CDR1",))
    row = rows[0]
    assert row["position"] == 10
    assert row["chain"] == "A"
    assert row["perplexity"] == pytest.approx(2.0)
    assert row["log_prob"] == pytest.approx(np.log(0.05))
    assert row["entropy"] == pytest.approx(np.log(20), rel=1e-6)
    assert row["is_cdr"] == 0


def test_runner_writes_score_table(monkeypatch, tmp_path):
    pdb_path = tmp_path / "one.pdb"
    pdb_path.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\nEND\n")
    weights = tmp_path / "model.pt"
    weights.write_bytes(b"x")
    monkeypatch.setattr(module, "load_scoring_model", lambda path: object())
    monkeypatch.setattr(module, "_import_antifold", lambda: object())
    monkeypatch.setattr(
        module,
        "_score_file",
        lambda model, antiscripts, structure_path, chain, batch_size: [_record("27"), _record("40", "G")],
    )
    monkeypatch.setattr(module, "score_dataframe_from_records", lambda records, regions: score_dataframe_from_records(records, regions))
    from src.task.context import Context as RealContext

    ctx = RealContext(str(tmp_path / "task"), {"params": {}})
    params = {
        "output": "scores",
        "structure_path": str(pdb_path),
        "chains": "A",
        "weights_path": str(weights),
        "device": "cpu",
        "imgt_regions": "CDR1,CDR2,CDR3",
    }
    run(ctx, [{"name": "antifold_score", "params": params}])
    form = ctx["scores"]
    assert form.dims == ["residue", "statistic"]
    assert form.data.shape == (2, 4)
    assert form.labels["residue"] == {"A:27": 0, "A:40": 1}
    assert form.info["cdr_residues"] == 1
    assert form.info["mean_perplexity"] == pytest.approx(2.0)


def test_validation_errors():
    with pytest.raises(StepError, match="structure_path is required"):
        module.AntifoldScoreStep().run(Ctx({"output": "s"}), [])
    with pytest.raises(StepError, match="is not a file"):
        module.AntifoldScoreStep().run(Ctx({"output": "s", "structure_path": "/nope.pdb", "chains": "A"}), [])
    import tempfile

    pdb_path = Path(tempfile.mkdtemp()) / "one.pdb"
    pdb_path.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\nEND\n")
    with pytest.raises(StepError, match="weights_path is required"):
        module.AntifoldScoreStep().run(
            Ctx({"output": "s", "structure_path": str(pdb_path), "chains": "A"}),
            [],
        )


def test_real_antifold_when_available():
    pytest.importorskip("antifold")
    import os

    weights = os.environ.get("OPERON_ANTIFOLD_WEIGHTS", "")
    if not weights or not os.path.isfile(weights):
        pytest.skip("OPERON_ANTIFOLD_WEIGHTS is not set")
    import tempfile

    from src.task.context import Context as RealContext

    ctx = RealContext(tempfile.mkdtemp(), {"params": {}})
    params = {
        "output": "scores",
        "structure_path": str(ROOT / "tests" / "fixtures" / "vhh_1mel.pdb"),
        "chains": "A",
        "weights_path": weights,
        "device": "cpu",
    }
    run(ctx, [{"name": "antifold_score", "params": params}])
    form = ctx["scores"]
    assert form.data.shape[0] == 132
    assert 1.0 < form.info["mean_perplexity"] < 10.0
