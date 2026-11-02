"""foldseek_search: command, parsing and gating."""

import sys
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.foldseek_search import FoldseekSearchStep, foldseek_command, parse_m8

FAKE = """import sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[3])
lines = [
    "q\ttargetA\t1e-10\t200.0\t0.99\t0.95\t0.94\t0.93",
    "q\ttargetB\t1e-05\t150.0\t0.90\t0.80\t0.81\t0.79",
]
out.write_text(chr(10).join(lines) + chr(10))
"""


def _form():
    rows = [(0.0, 0.0, 0.0, 1, "ALA", "A")]
    names = ("x", "y", "z", "residue_number", "resname", "chain")
    encoders = {}
    codes = {}
    for index, name in enumerate(names):
        if name in ("x", "y", "z", "residue_number"):
            continue
        encoder = LabelEncoder()
        encoded = encoder.fit_transform([str(row[index]) for row in rows])
        encoders[name] = encoder
        codes[name] = [float(code) for code in encoded]
    data = [[0.0, 0.0, 0.0, 1.0, codes["resname"][0], codes["chain"][0]]]
    return Form(data=__import__("numpy").asarray(data, dtype="float32"), dims=["atom", "field"], labels={"atom": {"a0": 0}, "field": {n: i for i, n in enumerate(names)}}, info={"missing_code": float("nan"), "encoders": {"field": encoders}})


def test_command_and_parse():
    command = foldseek_command("foldseek", Path("q.pdb"), Path("db"), Path("o.m8"), Path("tmp"), threads=4, max_hits=10)
    assert command[:2] == ["foldseek", "easy-search"]
    hits = parse_m8("q\ttA\t1e-10\t200\t0.99\t0.95\t0.94\t0.93\nq\ttB\t1e-5\t150\t0.9\t0.8\t0.81\t0.79\n")
    assert [hit["target"] for hit in hits] == ["tA", "tB"]
    assert hits[0]["alntmscore"] == pytest.approx(0.95)


def test_run_roundtrip(tmp_path):
    script = tmp_path / "foldseek"
    script.write_text("#!" + sys.executable + "\n" + FAKE)
    script.chmod(0o755)
    query = tmp_path / "query.pdb"
    query.write_text("ATOM")
    database = tmp_path / "db"
    database.mkdir()
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    params = {"output": "hits", "query_path": str(query), "database_path": str(database), "foldseek_path": str(script)}
    run(ctx, [{"name": "foldseek_search", "inputs": ["pdb"], "params": params}])
    result = ctx["hits"]
    assert result.data.shape == (2, 6)
    assert result.info["targets"][0] == "targetA"


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "foldseek_search", "inputs": ["pdb"], "params": {"output": "hits", "query_path": "/nope.pdb", "database_path": str(tmp_path)}}])
    query = tmp_path / "q.pdb"
    query.write_text("ATOM")
    with pytest.raises(StepError, match="does not exist"):
        run(ctx, [{"name": "foldseek_search", "inputs": ["pdb"], "params": {"output": "hits", "query_path": str(query), "database_path": str(tmp_path / "missingdb")}}])
