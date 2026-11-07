"""Tests for the LigandMPNN design operator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.step.steps import ligandmpnn_design as module
from src.task.step.steps.ligandmpnn_design import (
    LigandMpnnDesignStep,
    _parse_amino_acids,
    _parse_bias,
    _parse_residues,
    parse_design_fasta,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"

FAKE_RUNNER = r'''import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]


def value(flag):
    return args[args.index(flag) + 1] if flag in args else None


Path("captured.json").write_text(
    json.dumps({"argv": args, "cwd": str(Path.cwd()), "cuda": os.environ.get("CUDA_VISIBLE_DEVICES")})
)
pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
(out / "seqs").mkdir(parents=True, exist_ok=True)
stem = pdb.stem
lines = [
    ">%s, T=0.1, seed=1, num_res=4, num_ligand_res=0, use_ligand_context=True, "
    "ligand_cutoff_distance=8.0, batch_size=1, number_of_batches=2, model_path=x" % stem,
    "SG",
]
for index in (1, 2):
    confidence = 0.75 if index == 1 else 0.5
    ligand = 0.9 if index == 1 else 0.8
    recovery = 0.6 if index == 1 else 0.4
    lines.append(
        ">%s, id=%d, T=0.1, seed=1, overall_confidence=%.2f, ligand_confidence=%.2f, seq_rec=%.2f"
        % (stem, index, confidence, ligand, recovery)
    )
    lines.append("SG")
(out / "seqs" / (stem + ".fa")).write_text("\n".join(lines) + "\n")
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path, runner_name="run.py", weights_name="ligandmpnn_v_32_010_25.pt"):
    repo = tmp_path / "LigandMPNN"
    repo.mkdir()
    (repo / runner_name).write_text(FAKE_RUNNER)
    (repo / "model_params").mkdir()
    weights = repo / "model_params" / weights_name
    weights.write_text("stub weights")
    return repo, weights


def _run(params):
    params = {"python_executable": sys.executable, **params}
    ctx = Ctx(params)
    step = LigandMpnnDesignStep()
    step.run(ctx, [])
    return step, ctx["out"]


def _captured(repo):
    return json.loads((repo / "captured.json").read_text())


def _flag(argv, name):
    return argv[argv.index(name) + 1]


def test_design_outputs_and_sequences(tmp_path):
    repo, weights = _repo(tmp_path)
    _, out = _run(
        {
            "structure_path": str(FIXTURE),
            "ligandmpnn_path": str(repo),
            "weights_path": str(weights),
            "number_of_batches": 2,
            "batch_size": 1,
        }
    )
    assert list(out.dims) == ["design", "statistic"]
    assert list(out.labels["design"].keys()) == ["design1", "design2"]
    assert list(out.labels["statistic"].keys()) == ["overall_confidence", "ligand_confidence", "seq_recovery"]
    np.testing.assert_allclose(
        np.asarray(out.data),
        np.array([[0.75, 0.9, 0.6], [0.5, 0.8, 0.4]], dtype=np.float32),
        rtol=1e-6,
    )
    assert out.info["sequences"] == ["SG", "SG"]
    assert out.info["n_designs"] == 2
    assert out.info["metric"].startswith("confidence=")


def test_design_command_and_environment(tmp_path):
    repo, weights = _repo(tmp_path)
    _run(
        {
            "structure_path": str(FIXTURE),
            "ligandmpnn_path": str(repo),
            "weights_path": str(weights),
            "model_type": "protein_mpnn",
            "chains_to_design": "C",
            "fixed_positions": "C60 C61",
            "omit_AA": "CW",
            "bias_AA": "C:-1.0,W:0.5",
            "temperature": 0.2,
            "seed": 7,
            "number_of_batches": 1,
            "batch_size": 2,
        }
    )
    captured = _captured(repo)
    argv = captured["argv"]
    assert captured["cwd"] == str(repo)
    assert captured["cuda"] == ""
    assert _flag(argv, "--model_type") == "protein_mpnn"
    assert _flag(argv, "--checkpoint_protein_mpnn") == weights.as_posix()
    assert _flag(argv, "--pdb_path") == FIXTURE.as_posix()
    assert _flag(argv, "--temperature") == "0.2"
    assert _flag(argv, "--seed") == "7"
    assert _flag(argv, "--batch_size") == "2"
    assert _flag(argv, "--fixed_residues") == "C60 C61"
    assert _flag(argv, "--omit_AA") == "CW"
    assert _flag(argv, "--bias_AA") == "C:-1.0,W:0.5"
    assert _flag(argv, "--chains_to_design") == "C"
    assert "--redesigned_residues" not in argv


def test_design_redesigned_residues(tmp_path):
    repo, weights = _repo(tmp_path)
    _run(
        {
            "structure_path": str(FIXTURE),
            "ligandmpnn_path": str(repo),
            "weights_path": str(weights),
            "redesigned_residues": "C62,C63",
        }
    )
    captured = _captured(repo)
    assert _flag(captured["argv"], "--redesigned_residues") == "C62 C63"


def test_design_export_and_print(tmp_path, capsys):
    repo, weights = _repo(tmp_path)
    step, out = _run(
        {"structure_path": str(FIXTURE), "ligandmpnn_path": str(repo), "weights_path": str(weights)}
    )
    record = step.export(Ctx({}))
    assert record["designs"] == 2
    assert record["sequences"] == out.info["sequences"]
    assert "ligandmpnn_design: 2 designs" in capsys.readouterr().out


def test_residue_and_amino_acid_parsing():
    assert _parse_residues("C60 C61,C62", "fixed_positions") == ["C60", "C61", "C62"]
    with pytest.raises(StepError, match="is not of the form A12"):
        _parse_residues("60", "fixed_positions")
    with pytest.raises(StepError, match="is not an amino acid letter"):
        _parse_amino_acids("CB")
    assert _parse_amino_acids("CW") == "CW"
    assert _parse_bias("C:-1.0,P:2.5") == "C:-1.0,P:2.5"
    with pytest.raises(StepError, match="is not of the form A:-1.0"):
        _parse_bias("C-1.0")


def test_parse_design_fasta_rejects_bad_files(tmp_path):
    with pytest.raises(StepError, match="no FASTA file"):
        parse_design_fasta(tmp_path / "missing.fa")
    path = tmp_path / "empty.fa"
    path.write_text(">only_native, T=0.1, seed=1\nAAAA\n")
    with pytest.raises(StepError, match="no generated sequences"):
        parse_design_fasta(path)


def test_parameter_errors(tmp_path):
    repo, weights = _repo(tmp_path)
    base = {
        "structure_path": str(FIXTURE),
        "ligandmpnn_path": str(repo),
        "weights_path": str(weights),
    }
    with pytest.raises(StepError, match="structure_path is required"):
        _run({**base, "structure_path": ""})
    with pytest.raises(StepError, match="is not a file"):
        _run({**base, "structure_path": str(tmp_path / "missing.pdb")})
    (tmp_path / "notrepo").mkdir()
    with pytest.raises(StepError, match="does not look like a LigandMPNN checkout"):
        _run({**base, "ligandmpnn_path": str(tmp_path / "notrepo")})
    with pytest.raises(StepError, match="weights_path is required"):
        _run({**base, "weights_path": ""})
    with pytest.raises(StepError, match="model_type must be one of"):
        _run({**base, "model_type": "esm"})
    with pytest.raises(StepError, match="temperature must be in"):
        _run({**base, "temperature": 0.0})
    with pytest.raises(StepError, match="cannot be fixed and redesigned at once"):
        _run({**base, "fixed_positions": "C60", "redesigned_residues": "C60"})
    with pytest.raises(StepError, match="number_of_batches must be at least 1"):
        _run({**base, "number_of_batches": 0})
    with pytest.raises(StepError, match="timeout_seconds must be positive"):
        _run({**base, "timeout_seconds": 0})


def test_runner_failure_reports_stderr(tmp_path):
    repo, weights = _repo(tmp_path, runner_name="run.py")
    (repo / "run.py").write_text("import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n")
    with pytest.raises(StepError, match="exit code 3.*boom"):
        _run(
            {"structure_path": str(FIXTURE), "ligandmpnn_path": str(repo), "weights_path": str(weights)}
        )


def test_non_finite_confidences_are_rejected(tmp_path):
    repo, weights = _repo(tmp_path)
    runner = FAKE_RUNNER.replace(
        "confidence = 0.75 if index == 1 else 0.5", "confidence = float('nan')"
    )
    (repo / "run.py").write_text(runner)
    with pytest.raises(StepError, match="non-finite confidences"):
        _run(
            {"structure_path": str(FIXTURE), "ligandmpnn_path": str(repo), "weights_path": str(weights)}
        )


REPO = os.environ.get("OPERON_LIGANDMPNN_PATH", "")
WEIGHTS = os.environ.get("OPERON_LIGANDMPNN_WEIGHTS", "")
REAL = bool(REPO and WEIGHTS and Path(REPO, "run.py").is_file() and Path(WEIGHTS).is_file())


@pytest.mark.skipif(not REAL, reason="set OPERON_LIGANDMPNN_PATH and OPERON_LIGANDMPNN_WEIGHTS for the official oracle")
def test_official_runner_oracle(tmp_path):
    params = {
        "structure_path": str(FIXTURE),
        "ligandmpnn_path": REPO,
        "weights_path": WEIGHTS,
        "model_type": "ligand_mpnn",
        "temperature": 0.1,
        "seed": 1,
        "number_of_batches": 1,
        "batch_size": 1,
    }
    _, out = _run(params)
    assert out.data.shape == (1, 3)
    assert 0.0 < float(out.data[0, 0]) <= 1.0
    assert 0.0 <= float(out.data[0, 2]) <= 1.0
    assert len(out.info["sequences"][0]) == 16

    # independent official run with the same settings
    target = tmp_path / "manual"
    command = [
        sys.executable,
        str(Path(REPO) / "run.py"),
        "--pdb_path",
        FIXTURE.as_posix(),
        "--out_folder",
        target.as_posix(),
        "--model_type",
        "ligand_mpnn",
        "--checkpoint_ligand_mpnn",
        Path(WEIGHTS).as_posix(),
        "--temperature",
        "0.1",
        "--seed",
        "1",
        "--number_of_batches",
        "1",
        "--batch_size",
        "1",
    ]
    subprocess.run(
        command,
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": ""},
    )
    records = parse_design_fasta(target / "seqs" / f"{FIXTURE.stem}.fa")
    assert [record["overall_confidence"] for record in records] == pytest.approx(
        [float(value) for value in out.data[:, 0]], rel=1e-5
    )
    assert [record["sequence"] for record in records] == out.info["sequences"]
