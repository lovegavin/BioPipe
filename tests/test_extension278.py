"""proteinmpnn_interface_scan: cutoff sweep over hotspot-masked design."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_interface_scan import parse_cutoffs

FAKE = """import sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out_folder") + 1])
stem = Path(args[args.index("--pdb_path") + 1]).stem
(out / "seqs").mkdir(parents=True, exist_ok=True)
text = ">T=" + stem + ", sample=1, score=1.5, global_score=1.8, seq_recovery=0.5" + chr(10) + "AAAA" + chr(10)
(out / "seqs" / (stem + ".fa")).write_text(text)
"""


def _pdb() -> str:
    lines = ["ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C"]
    for index in range(2, 5):
        lines.append(f"ATOM  {index:5d}  CA  ALA A{index:4d}       3.000   0.000   0.000  1.00  0.00           C")
    lines.append("ATOM      9  CA  ALA B   1       4.000   0.000   0.000  1.00  0.00           C")
    lines.append("END")
    return "\n".join(lines) + "\n"


def _form(rows):
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
    data = []
    for row_index, row in enumerate(rows):
        values = []
        for name, value in zip(names, row):
            if name in ("x", "y", "z", "residue_number"):
                values.append(float(value))
            else:
                values.append(codes[name][row_index])
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"a{i}": i for i in range(len(rows))},
            "field": {name: i for i, name in enumerate(names)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _rows():
    rows = [(0.0, 0.0, 0.0, 1, "ALA", "A"), (3.0, 0.0, 0.0, 2, "ALA", "A"), (4.0, 0.0, 0.0, 1, "ALA", "B")]
    return rows


def test_parse_cutoffs():
    assert parse_cutoffs("4.0, 4.5;5.0") == [4.0, 4.5, 5.0]
    with pytest.raises(StepError, match="not a number"):
        parse_cutoffs("4,x")


def test_run_sweeps_cutoffs(tmp_path):
    repo = Path(tmp_path / "mpnn")
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE.replace('sys.argv', 'sys.argv'))
    structure = Path(tmp_path / "mini.pdb")
    structure.write_text(_pdb())
    form = _form(_rows())
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    params = {
        "output": "scan",
        "structure_path": str(structure),
        "binder_chains": "A",
        "target_chains": "B",
        "cutoffs": "4.0,5.0",
        "proteinmpnn_path": str(repo),
        "weights_path": str(repo / "vanilla_model_weights"),
        "python_executable": sys.executable,
    }
    run(ctx, [{"name": "proteinmpnn_interface_scan", "inputs": ["pdb"], "params": params}])
    result = ctx["scan"]
    assert result.dims == ["cutoff", "statistic"]
    assert result.data.shape[0] == 2
    assert result.info["n_cutoffs"] == 2


def test_missing_structure_is_rejected(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _form(_rows())
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "proteinmpnn_interface_scan", "inputs": ["pdb"], "params": {"output": "scan", "structure_path": str(tmp_path / "nope.pdb"), "cutoffs": "4.0"}}])
