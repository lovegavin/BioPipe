"""Tests for proteinmpnn_position_entropy."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.proteinmpnn_position_entropy import (
    ProteinmpnnPositionEntropyStep,
    designer_command,
    position_entropy,
    read_fasta,
    split_designs,
)

REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")
REAL_WEIGHTS = REAL_REPO / "vanilla_model_weights" / "v_48_020.pt"
FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"

NATIVE = "ACDEFG"


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


FAKE_RUNNER = "\n".join(
    [
        "import json, sys",
        "from pathlib import Path",
        "args = sys.argv[1:]",
        "def value(flag):",
        "    return args[args.index(flag) + 1]",
        "out = Path(value('--out_folder'))",
        "structure = Path(value('--pdb_path'))",
        "(out / 'seqs').mkdir(parents=True, exist_ok=True)",
        "native = 'ACDEFG'",
        "designs = ['ACDEFG', 'ACDEFY', 'ACDEAA', 'ACDEFG']",
        "lines = ['>1abc, score=1.0, seed=1', native]",
        "for index, design in enumerate(designs, start=1):",
        "    lines.append(f'>T=0.1, sample={index}, score={index/10:.4f}, global_score=1.0, seq_recovery=0.5')",
        "    lines.append(design)",
        "(out / 'seqs' / (structure.stem + '.fa')).write_text('\\n'.join(lines) + '\\n')",
        "json.dump({'argv': args, 'cwd': str(Path.cwd())}, open(Path.cwd() / 'captured.json', 'w'))",
        "",
    ]
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True, exist_ok=True)
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"stub")
    return repo


def _structure(tmp_path: Path) -> Path:
    path = tmp_path / "1abc.pdb"
    path.write_text("HEADER    TEST\nEND\n", encoding="utf-8")
    return path


def _run(params: dict) -> Ctx:
    ctx = Ctx(params)
    step = ProteinmpnnPositionEntropyStep()
    step.run(ctx, [])
    ctx.step = step
    return ctx


def test_position_entropy_hand_values() -> None:
    designs = ["ACDEFG", "ACDEFY", "ACDEAA", "ACDEFG"]
    rows = position_entropy(designs, NATIVE)
    assert len(rows) == 6
    assert rows[0]["entropy_bits"] == pytest.approx(0.0)
    assert rows[5]["entropy_bits"] == pytest.approx(1.5)
    assert rows[5]["recovery"] == pytest.approx(0.5)
    assert rows[5]["max_frequency"] == pytest.approx(0.5)
    assert rows[5]["consensus"] == "G"
    assert rows[5]["n_observed"] == 4


def test_read_fasta_and_split(tmp_path: Path) -> None:
    path = tmp_path / "designs.fa"
    path.write_text(">meta\nACD\n>T=0.1\nACD\n>T=0.1\nACE\n", encoding="utf-8")
    native, designs = split_designs(read_fasta(path))
    assert native == "ACD"
    assert designs == ["ACD", "ACE"]
    single = tmp_path / "single.fa"
    single.write_text(">meta\nACD\n", encoding="utf-8")
    with pytest.raises(StepError, match="no generated designs"):
        split_designs(read_fasta(single))


def test_designer_command(tmp_path: Path) -> None:
    structure = tmp_path / "ab cd.pdb"
    out_dir = tmp_path / "out"
    repo = tmp_path / "repo"
    command = designer_command(
        repo,
        structure,
        out_dir,
        {
            "python_executable": "/usr/bin/python3",
            "weights_path": str(tmp_path / "weights"),
            "num_seq_per_target": 4,
            "sampling_temp": 0.1,
            "seed": 1,
            "model_name": "v_48_020",
            "chains": "A,B",
        },
    )
    assert command[0] == "/usr/bin/python3"
    assert command[1] == "protein_mpnn_run.py"
    assert "--pdb_path" in command
    assert command[command.index("--pdb_path") + 1].endswith("ab cd.pdb")
    assert command[command.index("--num_seq_per_target") + 1] == "4"
    assert command[command.index("--model_name") + 1] == "v_48_020"
    assert "--pdb_path_chains" in command


def test_step_output_and_capture(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    ctx = _run(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo),
            "weights_path": str(repo / "vanilla_model_weights"),
            "num_seq_per_target": 4,
            "sampling_temp": "0.1",
            "seed": 1,
            "model_name": "v_48_020",
            "chains": "A",
            "device": "cpu",
            "output": "entropy",
        }
    )
    out = ctx["entropy"]
    assert out.data.shape == (6, 4)
    assert list(out.labels["statistic"]) == [
        "entropy_bits",
        "recovery",
        "max_frequency",
        "n_observed",
    ]
    assert out.labels["position"]["6"] == 5
    assert out.data[5, 0] == pytest.approx(1.5, abs=1e-6)
    assert out.data[0, 0] == pytest.approx(0.0)
    assert out.info["native_sequence"] == NATIVE
    assert out.info["num_samples"] == 4
    assert out.info["consensus"] == ["A", "C", "D", "E", "F", "G"]
    exported = ctx.step.export(ctx)
    assert exported["positions"] == 6
    assert exported["num_samples"] == 4
    captured = json.loads((repo / "captured.json").read_text(encoding="utf-8"))
    assert captured["cwd"] == str(repo.resolve())


def test_parameter_errors(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    base = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "device": "cpu",
        "output": "out",
    }
    with pytest.raises(StepError, match="structure_path must point"):
        _run({**base, "structure_path": str(tmp_path / "missing.pdb")})
    with pytest.raises(StepError, match="must contain protein_mpnn_run.py"):
        _run({**base, "proteinmpnn_path": str(tmp_path / "empty")})
    with pytest.raises(StepError, match="model_name must be one of"):
        _run({**base, "model_name": "v_99_999"})
    with pytest.raises(StepError, match="num_seq_per_target must be at least 2"):
        _run({**base, "num_seq_per_target": 1})
    with pytest.raises(StepError, match="sampling_temp must be in"):
        _run({**base, "sampling_temp": "0"})
    with pytest.raises(StepError, match="seed must not be negative"):
        _run({**base, "seed": -1})
    with pytest.raises(StepError, match="device must be"):
        _run({**base, "device": "tpu"})


def test_runner_failures(tmp_path: Path) -> None:
    repo = tmp_path / "failed"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(
        "import sys\nsys.stderr.write('boom')\nsys.exit(3)\n", encoding="utf-8"
    )
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="exit code 3"):
        _run(
            {
                "structure_path": str(structure),
                "proteinmpnn_path": str(repo),
                "device": "cpu",
                "output": "out",
            }
        )
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "protein_mpnn_run.py").write_text(
        "import sys\nfrom pathlib import Path\nout = Path(sys.argv[sys.argv.index('--out_folder') + 1])\n"
        "(out / 'seqs').mkdir(parents=True, exist_ok=True)\n",
        encoding="utf-8",
    )
    with pytest.raises(StepError, match="produced no FASTA"):
        _run(
            {
                "structure_path": str(structure),
                "proteinmpnn_path": str(empty),
                "device": "cpu",
                "output": "out",
            }
        )


def test_position_entropy_rejects_bad_designs() -> None:
    with pytest.raises(StepError, match="must match the native length"):
        position_entropy(["ACD", "ACDEF"], "ACDEFG")
    with pytest.raises(StepError, match="not a standard amino acid"):
        position_entropy(["ACD?FG"], "ACDEFG")


@pytest.mark.skipif(
    not (REAL_REPO / "protein_mpnn_run.py").is_file() or not REAL_WEIGHTS.is_file(),
    reason="local ProteinMPNN checkout and v_48_020 weights are required",
)
def test_real_designer_entropy(tmp_path: Path) -> None:
    import shutil
    import sys

    checkpoint = tmp_path / "repo"
    shutil.copytree(
        REAL_REPO,
        checkpoint,
        ignore=shutil.ignore_patterns("outputs", "*.pt", "training", "examples"),
    )
    ctx = _run(
        {
            "structure_path": str(FIXTURE),
            "proteinmpnn_path": str(checkpoint),
            "weights_path": str(REAL_WEIGHTS.parent),
            "python_executable": sys.executable,
            "num_seq_per_target": 4,
            "sampling_temp": "0.1",
            "seed": 1,
            "model_name": "v_48_020",
            "chains": "C",
            "device": "cpu",
            "timeout": 600,
            "output": "entropy",
        }
    )
    out = ctx["entropy"]
    assert out.data.shape == (16, 4)
    assert np.isfinite(out.data).all()
    assert (out.data[:, 3] == 4).all()
    assert out.info["num_samples"] == 4
    assert len(out.info["native_sequence"]) == 16
