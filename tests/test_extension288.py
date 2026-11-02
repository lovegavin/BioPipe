"""proteinmpnn_interface_temperature_scan: temperature ladder."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_interface_temperature_scan import parse_temperatures, scan_rows

FAKE = """import sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out_folder") + 1])
stem = Path(args[args.index("--pdb_path") + 1]).stem
temp = args[args.index("--sampling_temp") + 1]
(out / "seqs").mkdir(parents=True, exist_ok=True)
score = 1.0 if temp == "0.1" else 2.0
text = ">T=" + stem + ", sample=1, score=" + str(score) + ", global_score=" + str(score + 0.5) + ", seq_recovery=0.5" + chr(10) + "AAAA" + chr(10)
(out / "seqs" / (stem + ".fa")).write_text(text)
"""


def _pdb() -> str:
    lines = ["ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C"]
    lines.append("ATOM      2  CA  ALA A   2       3.000   0.000   0.000  1.00  0.00           C")
    lines.append("ATOM      3  CA  ALA B   1       4.000   0.000   0.000  1.00  0.00           C")
    return "\n".join(lines) + "\nEND\n"


def _form():
    encoders = {}
    names = ("x", "y", "z", "residue_number", "resname", "chain")
    rows = [(0.0, 0.0, 0.0, 1, "ALA", "A"), (3.0, 0.0, 0.0, 2, "ALA", "A"), (4.0, 0.0, 0.0, 1, "ALA", "B")]
    codes = {}
    for index, name in enumerate(names):
        if name in ("x", "y", "z", "residue_number"):
            continue
        encoder = LabelEncoder()
        encoded = encoder.fit_transform([str(row[index]) for row in rows])
        encoders[name] = encoder
        codes[name] = [float(code) for code in encoded]
    data = []
    for row_index, row in enumerate(rows):
        values = []
        for name, value in zip(names, row):
            values.append(float(value) if name in ("x", "y", "z", "residue_number") else codes[name][row_index])
        data.append(values)
    return Form(data=np.asarray(data, dtype=np.float32), dims=["atom", "field"], labels={"atom": {f"a{i}": i for i in range(3)}, "field": {n: i for i, n in enumerate(names)}}, info={"missing_code": np.nan, "encoders": {"field": encoders}})


def test_parse_temperatures():
    assert parse_temperatures("0.1,0.2;0.3") == [0.1, 0.2, 0.3]
    with pytest.raises(StepError, match="not a number"):
        parse_temperatures("0.1,x")
    with pytest.raises(StepError, match="must be in"):
        parse_temperatures("1.5")


def test_scan_rows_summary():
    records = [
        {"score": 1.0, "global_score": 1.5, "seq_recovery": 0.4},
        {"score": 2.0, "global_score": 2.5, "seq_recovery": 0.6},
    ]
    row = scan_rows(records, 0.2)
    assert row["n_designs"] == 2
    assert row["mean_score"] == pytest.approx(1.5)
    assert row["mean_recovery"] == pytest.approx(0.5)
    with pytest.raises(StepError, match="no design was generated"):
        scan_rows([], 0.2)


def test_run_scans_temperatures(tmp_path):
    repo = Path(tmp_path / "mpnn")
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE)
    structure = Path(tmp_path / "mini.pdb")
    structure.write_text(_pdb())
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form()
    params = {
        "output": "scan",
        "structure_path": str(structure),
        "binder_chains": "A",
        "target_chains": "B",
        "temperatures": "0.1,0.2",
        "proteinmpnn_path": str(repo),
        "weights_path": str(repo / "vanilla_model_weights"),
        "python_executable": sys.executable,
    }
    run(ctx, [{"name": "proteinmpnn_interface_temperature_scan", "inputs": ["pdb"], "params": params}])
    result = ctx["scan"]
    assert result.data.shape[0] == 2
    assert result.data[0, 1] < result.data[1, 1]
    assert result.info["temperatures"] == [0.1, 0.2]
