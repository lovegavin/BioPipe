"""Tests for the ColabFold wrapper operator."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.colabfold_predict import (
    ColabfoldPredictStep,
    parse_scores,
    rank_pdb,
    write_fasta,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "backbone_1bc8_c60_75.pdb"
SEQUENCE = "ACDEFGHIK"

FAKE_RUNNER = '''#!/usr/bin/env python
import json
import os
import shutil
import sys
from pathlib import Path

arguments = sys.argv[1:]
fasta = Path(arguments[0])
outdir = Path(arguments[1])
outdir.mkdir(parents=True, exist_ok=True)
sequence = "".join(line.strip() for line in fasta.read_text().splitlines() if not line.startswith(">"))
shutil.copy(os.environ["OPERON_TEST_PDB"], outdir / "query_unrelaxed_rank_001_alphafold2_ptm_model_1_seed_000.pdb")
(outdir / "query_scores_rank_001_alphafold2_ptm_model_1_seed_000.json").write_text(
    json.dumps({"plddt": [91.0, 84.0, 77.0], "ptm": 0.83, "pae": [[0.0, 4.0], [4.0, 0.0]], "max_pae": 4.0})
)
if os.environ.get("OPERON_TEST_CAPTURE"):
    Path(os.environ["OPERON_TEST_CAPTURE"]).write_text(
        json.dumps({"argv": arguments, "sequence": sequence})
    )
'''


def _script(tmp_path: Path, body: str = FAKE_RUNNER) -> Path:
    path = tmp_path / "fake_colabfold.py"
    text = body.split("\n", 1)[1] if body.startswith("#!") else body
    path.write_text(f"#!{sys.executable}\n" + text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _params(script: Path, **overrides):
    params = {"colabfold_path": str(script), "device": "cpu", "num_models": 1, "num_recycles": 2}
    params.update(overrides)
    return params


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = dict(params or {})
        self.metadata = {}


def test_helper_functions(tmp_path) -> None:
    fasta = write_fasta(SEQUENCE, tmp_path / "query.fasta")
    assert fasta.read_text() == f">query\n{SEQUENCE}\n"

    outdir = tmp_path / "out"
    outdir.mkdir()
    assert rank_pdb(outdir) is None
    (outdir / "query_unrelaxed_rank_001_model.pdb").write_text("ATOM\n")
    (outdir / "query_relaxed_rank_001_model.pdb").write_text("ATOM\n")
    assert rank_pdb(outdir).name == "query_relaxed_rank_001_model.pdb"

    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps({"plddt": [80.0, 90.0], "ptm": 0.7, "pae": [[0, 1], [2, 0]], "max_pae": 2.0}))
    parsed = parse_scores(scores)
    assert parsed == {"mean_plddt": 85.0, "ptm": 0.7, "max_pae": 2.0, "n_residues": 2}


def test_prediction_parses_structure_and_scores(tmp_path, monkeypatch) -> None:
    script = _script(tmp_path)
    capture = tmp_path / "capture.json"
    monkeypatch.setenv("OPERON_TEST_PDB", str(FIXTURE))
    monkeypatch.setenv("OPERON_TEST_CAPTURE", str(capture))

    ctx = Ctx(_params(script, output="structure"))
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    ColabfoldPredictStep().run(ctx, [form])
    out = ctx["structure"]
    assert out.dims == ["atom", "field"]
    assert out.info["mean_plddt"] == pytest.approx(84.0)
    assert out.info["ptm"] == pytest.approx(0.83)
    assert out.info["max_pae"] == pytest.approx(4.0)
    assert out.info["n_residues"] == 3
    assert out.info["sequences"] == [SEQUENCE]
    assert out.info["msa_mode"] == "mmseqs2_uniref_env"

    recorded = json.loads(capture.read_text())
    assert recorded["sequence"] == SEQUENCE
    argv = recorded["argv"]
    assert "--msa-mode" in argv and "--num-recycle" in argv
    assert "--num-models" in argv and argv[argv.index("--num-models") + 1] == "1"
    assert "--num-recycle" in argv and argv[argv.index("--num-recycle") + 1] == "2"


def test_missing_binary_is_reported(tmp_path) -> None:
    ctx = Ctx({"colabfold_path": str(tmp_path / "missing")})
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    with pytest.raises(StepError, match="was not found on PATH"):
        ColabfoldPredictStep().run(ctx, [form])


def test_only_one_sequence_is_supported() -> None:
    with pytest.raises(StepError, match="exactly one sequence"):
        ColabfoldPredictStep().run(
            Ctx({"colabfold_path": "/bin/true"}),
            [encode_sequences(["ACD", "EFG"], "sequence", "position", "protein")],
        )


def test_failed_runner_and_missing_output(tmp_path, monkeypatch) -> None:
    failing = _script(tmp_path, "#!/usr/bin/env python\nimport sys\nsys.exit(3)\n")
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    with pytest.raises(StepError, match="exit code 3"):
        ColabfoldPredictStep().run(Ctx(_params(failing)), [form])

    silent = _script(tmp_path, "#!/usr/bin/env python\nimport sys\nfrom pathlib import Path\nPath(sys.argv[2]).mkdir(parents=True, exist_ok=True)\n")
    with pytest.raises(StepError, match="no rank-001 structure"):
        ColabfoldPredictStep().run(Ctx(_params(silent)), [form])


def test_invalid_msa_mode_is_rejected(tmp_path) -> None:
    script = _script(tmp_path)
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    with pytest.raises(StepError, match="msa_mode"):
        ColabfoldPredictStep().run(Ctx(_params(script, msa_mode="bogus")), [form])


def test_runner_round_trip(tmp_path, monkeypatch) -> None:
    script = _script(tmp_path)
    monkeypatch.setenv("OPERON_TEST_PDB", str(FIXTURE))
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    run(
        ctx,
        [
            {
                "name": "colabfold_predict",
                "inputs": ["sequence"],
                "params": {"colabfold_path": str(script), "output": "structure"},
            }
        ],
    )
    assert ctx["structure"].info["mean_plddt"] == pytest.approx(84.0)
    assert list((tmp_path / "task").rglob("*colabfold_predict*.json"))
