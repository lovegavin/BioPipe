"""boltz_complex_confidence: YAML, parsing and runner contract."""

import json
import sys

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.boltz_complex_confidence import (
    BoltzComplexConfidenceStep,
    boltz_command,
    interface_rows,
    parse_confidence,
    write_yaml,
)

_FIXTURE = """ATOM      1  N   GLN A   2      11.000  10.000  10.000  1.00 80.00           N
ATOM      2  CA  GLN A   2      11.000  10.000  11.000  1.00 80.00           C
ATOM      3  C   GLN A   2      12.000  10.000  11.000  1.00 80.00           C
ATOM      4  N   LYS B   1      11.000  10.000  13.000  1.00 60.00           N
ATOM      5  CA  LYS B   1      11.000  10.000  14.000  1.00 60.00           C
END
"""


def _pdb(tmp_path):
    path = tmp_path / "pred_model_0.pdb"
    path.write_text(_FIXTURE)
    return path


def test_yaml_and_command(tmp_path):
    yaml_path = tmp_path / "cx.yaml"
    write_yaml(yaml_path, "A", "MKVLA")
    assert "msa: empty" in yaml_path.read_text()
    command = boltz_command("boltz", yaml_path, tmp_path / "out", model="boltz2", device="cpu", sampling_steps=20, diffusion_samples=1, cache_dir="/tmp/cache")
    assert "--model" in command and "boltz2" in command and "--cache" in command


def test_parse_confidence(tmp_path):
    path = tmp_path / "confidence_x_model_0.json"
    path.write_text(json.dumps({
        "confidence_score": 0.72,
        "ptm": 0.31,
        "iptm": 0.44,
        "complex_plddt": 0.81,
        "pair_chains_iptm": {"0": {"0": 0.31, "1": 0.44}, "1": {"0": 0.44, "1": 0.31}},
    }))
    parsed = parse_confidence(path)
    assert parsed["iptm"] == 0.44 and parsed["chain_pair_iptm"] == 0.44


def test_interface_rows(tmp_path):
    order, mask = interface_rows(_pdb(tmp_path), cutoff=8.0)
    assert len(order) == 2
    assert mask == [True, True]


def test_run_round_trip(tmp_path, monkeypatch):
    form = encode_sequences(["MKVLA", "GGGS"], "sequence", "position", "protein")
    script = tmp_path / "boltz.py"
    script.write_text(
        "#!/usr/bin/env python\n"
        "import json, pathlib, sys\n"
        "out = pathlib.Path(sys.argv[sys.argv.index('--out_dir') + 1])\n"
        "pred = out / 'predictions' / 'job'\n"
        "pred.mkdir(parents=True)\n"
        "(pred / 'job_model_0.pdb').write_text(" + repr(_FIXTURE) + ")\n"
        "(pred / 'confidence_job_model_0.json').write_text(json.dumps({'iptm': 0.5, 'ptm': 0.4, 'complex_plddt': 0.8, 'pair_chains_iptm': {'0': {'1': 0.5}}}))\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequences"] = form
    run(ctx, [{"name": "boltz_complex_confidence", "inputs": ["sequences"], "params": {"output": "confidence", "boltz_path": str(script), "sampling_steps": 20}}])
    result = ctx["confidence"]
    assert result.data.shape == (2, 2)
    assert result.info["n_interface"] == 2
    assert result.info["chain_pair_iptm"] == 0.5


def test_errors(tmp_path):
    ctx = Context(str(tmp_path / "t"), {"params": {}})
    ctx["sequences"] = encode_sequences(["MKVLA"], "sequence", "position", "protein")
    with pytest.raises(StepError, match="expected exactly two sequences"):
        run(ctx, [{"name": "boltz_complex_confidence", "inputs": ["sequences"], "params": {"output": "confidence", "boltz_path": "boltz"}}])
