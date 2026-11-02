"""boltz_predict: YAML, invocation and output parsing."""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.boltz_predict import (
    BoltzPredictStep,
    boltz_command,
    find_outputs,
    parse_affinity,
    parse_confidence,
    write_yaml,
)

FAKE = """import json, sys
from pathlib import Path
args = sys.argv[1:]
out = Path(args[args.index("--out_dir") + 1])
base = out / "boltz_results_input" / "predictions" / "input"
base.mkdir(parents=True, exist_ok=True)
(base / "input_model_0.pdb").write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C" + chr(10))
(base / "confidence_input_model_0.json").write_text(json.dumps({"confidence_score": 0.81, "ptm": 0.72, "iptm": 0.63, "complex_plddt": 0.9}))
if "--affinity" in args:
    (base / "affinity_input_model_0.json").write_text(json.dumps({"affinity_pred_value": -1.25, "affinity_probability_binary": 0.77}))
"""


def test_write_yaml(tmp_path):
    path = tmp_path / "input.yaml"
    write_yaml(path, "MKVLA", chain="A")
    text = path.read_text()
    assert "protein:" in text and "sequence: MKVLA" in text
    write_yaml(path, "MKVLA", ligand_smiles="CCO", affinity=True)
    text = path.read_text()
    assert "ligand:" in text and "CCO" in text and "affinity:" in text
    with pytest.raises(StepError, match="affinity requires a ligand_smiles"):
        write_yaml(path, "MKVLA", affinity=True)


def test_command_and_parsing(tmp_path):
    command = boltz_command("boltz", tmp_path / "i.yaml", tmp_path / "out")
    assert command[:2] == ["boltz", "predict"]
    assert "--use_msa_server" in command
    base = tmp_path / "out" / "r" / "p" / "x"
    base.mkdir(parents=True)
    (base / "x_model_0.pdb").write_text("ATOM")
    (base / "confidence_x_model_0.json").write_text(json.dumps({"confidence_score": 0.5, "ptm": 0.4, "iptm": float("nan")}))
    outputs = find_outputs(tmp_path / "out")
    assert outputs["pdb"].name == "x_model_0.pdb"
    parsed = parse_confidence(outputs["confidence"])
    assert parsed["confidence_score"] == pytest.approx(0.5)
    assert np.isnan(parse_affinity(None)["affinity_pred_value"])


def test_run_roundtrip(tmp_path):
    script = tmp_path / "boltz"
    script.write_text("#!" + sys.executable + "\n" + FAKE)
    script.chmod(0o755)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences(["MKVLA"], "sequence", "position", "protein")
    params = {"output": "structure", "boltz_path": str(script), "ligand_smiles": "CCO", "affinity": True, "use_msa_server": False}
    run(ctx, [{"name": "boltz_predict", "inputs": ["sequence"], "params": params}])
    result = ctx["structure"]
    assert result.data.shape == (1, 6)
    assert result.data[0, 0] == pytest.approx(0.81)
    assert result.data[0, 4] == pytest.approx(-1.25)
    assert result.info["ligand"] is True


def test_missing_binary():
    ctx = Context("/tmp/bp292", {"params": {}})
    ctx["sequence"] = encode_sequences(["MKVLA"], "sequence", "position", "protein")
    with pytest.raises(StepError, match="was not found"):
        run(ctx, [{"name": "boltz_predict", "inputs": ["sequence"], "params": {"output": "s", "boltz_path": "/nonexistent/boltz"}}])
