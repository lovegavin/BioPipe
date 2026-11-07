"""openfold_predict: command construction, parsing and contract."""

import os
import sys
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.openfold_predict import (
    find_prediction,
    openfold_command,
    write_alignment,
    write_fasta,
)

PDB = """ATOM      1  N   MET A   1       0.000   0.000   0.000  1.00 70.00           N
ATOM      2  CA  MET A   1       1.458   0.000   0.000  1.00 80.00           C
ATOM      3  C   MET A   1       2.009   1.420   0.000  1.00 75.00           C
END
"""

RUNNER = """import shutil, sys
from pathlib import Path
out = Path(sys.argv[sys.argv.index("--output_dir") + 1]) / "predictions"
out.mkdir(parents=True, exist_ok=True)
here = Path(__file__).resolve().parent
shutil.copyfile(here / "expected.pdb", out / "q_model_1_ptm_unrelaxed.pdb")
"""


def test_write_helpers(tmp_path):
    fasta = tmp_path / "q.fasta"
    write_fasta(fasta, "MKVLA")
    assert fasta.read_text() == ">query\nMKVLA\n"
    folder = write_alignment(tmp_path / "align", "MKVLA")
    assert (folder / "uniref90_hits.a3m").read_text().startswith(">query")


def test_command_contract(tmp_path):
    command = openfold_command(sys.executable, tmp_path / "run.py", tmp_path / "fasta", tmp_path / "templates", tmp_path / "align", tmp_path / "out", params=tmp_path / "params.pt")
    assert command[0] == sys.executable
    assert command[command.index("--config_preset") + 1] == "model_1_ptm"
    assert command[command.index("--model_device") + 1] == "cpu"
    assert "--skip_relaxation" in command


def test_find_prediction_error(tmp_path):
    with pytest.raises(StepError, match="no prediction PDB"):
        find_prediction(tmp_path)


def _setup(tmp_path):
    repo = tmp_path / "openfold"
    repo.mkdir()
    (repo / "run_pretrained_openfold.py").write_text(RUNNER)
    (repo / "expected.pdb").write_text(PDB)
    weights = tmp_path / "params.pt"
    weights.write_text("x")
    return repo, weights


def _params(repo, weights):
    return {"output": "structure", "openfold_path": str(repo), "params_path": str(weights), "python_executable": sys.executable}


def test_run_matches_contract(tmp_path):
    repo, weights = _setup(tmp_path)
    form = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "openfold_predict", "inputs": ["sequence"], "params": _params(repo, weights)}])
    result = ctx["structure"]
    assert result.dims == ["atom", "field"]
    assert result.data.shape[0] == 3


def test_errors(tmp_path):
    repo, weights = _setup(tmp_path)
    form = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    with pytest.raises(StepError, match="openfold_path"):
        run(ctx, [{"name": "openfold_predict", "inputs": ["sequence"], "params": {**_params(repo, weights), "openfold_path": str(tmp_path / "missing")}}])
    with pytest.raises(StepError, match="params_path"):
        run(ctx, [{"name": "openfold_predict", "inputs": ["sequence"], "params": {**_params(repo, weights), "params_path": str(tmp_path / "missing.pt")}}])


@pytest.mark.skipif(os.environ.get("OPERON_OPENFOLD_REAL") != "1", reason="set OPERON_OPENFOLD_REAL=1 for a real OpenFold run")
def test_real_openfold(tmp_path):
    repo = Path(os.environ.get("OPERON_OPENFOLD_PATH", "/home/gavin/tools/openfold"))
    weights = Path(os.environ.get("OPERON_OPENFOLD_PARAMS", "/home/gavin/models/openfold/finetuning_ptm_2.pt"))
    if not (repo / "run_pretrained_openfold.py").is_file() or not weights.is_file():
        pytest.skip("OpenFold checkout or weights are missing")
    form = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    run(ctx, [{"name": "openfold_predict", "inputs": ["sequence"], "params": {"output": "structure", "openfold_path": str(repo), "params_path": str(weights), "python_executable": sys.executable, "device": "cpu"}}])
    result = ctx["structure"]
    assert result.data.shape[0] >= 40
    assert result.data.shape[1] >= 12
