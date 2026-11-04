"""Tests for the ProteinMPNN native recovery scan operator."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_native_recovery_scan import (
    ProteinmpnnNativeRecoveryScanStep,
    read_records,
    recovery_rows,
)

REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")

FAKE_RUNNER = r'''
import sys
from pathlib import Path

args = sys.argv[1:]
def value(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default

pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
count = int(value("--num_seq_per_target", "2"))

lines = ["{}" .format(">complex.pdb, score=1.1, global_score=1.2, fixed_chains=[], designed_chains=['A'], model_name=v_48_020, seed=1")]
lines.append("ACD")
for index in range(1, count + 1):
    lines.append(
        ">T=0.1, sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=1." + str(index) + ", seq_recovery=0.5"
    )
    lines.append("ACW" if index % 2 else "ACD")
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
(seqs / (pdb.stem + ".fa")).write_text("\n".join(lines) + "\n")
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "recovery", **params}
        self.metadata = {}


def _repo(root: Path) -> Path:
    repo = root / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    return repo


def test_read_records(tmp_path: Path) -> None:
    path = tmp_path / "seqs.fa"
    path.write_text(">native, score=1.0\nACD\n>T=0.1, sample=1\nACW\n>T=0.1, sample=2\nACD\n")
    records = read_records(path)
    assert [sequence for _, sequence in records] == ["ACD", "ACW", "ACD"]
    empty = tmp_path / "empty.fa"
    empty.write_text("")
    with pytest.raises(StepError, match="no FASTA records"):
        read_records(empty)


def test_recovery_rows_hand_values() -> None:
    rows = recovery_rows("ACD", ["ACD", "ACW", "ACW"])
    assert [row["recovery"] for row in rows] == [1.0, 1.0, pytest.approx(1 / 3)]
    assert rows[2]["dominant_frequency"] == pytest.approx(2 / 3)
    assert rows[2]["dominant_substitution"] == "W"
    assert rows[2]["consensus"] == "W"
    assert rows[2]["n_observed"] == 3.0


def test_recovery_rows_errors() -> None:
    with pytest.raises(StepError, match="no generated designs"):
        recovery_rows("ACD", [])
    with pytest.raises(StepError, match="does not match the native length"):
        recovery_rows("ACD", ["AC"])
    with pytest.raises(StepError, match="non-standard residue"):
        recovery_rows("ACD", ["ACX"])


def test_step_with_fake_runner(tmp_path: Path) -> None:
    structure = tmp_path / "complex.pdb"
    structure.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    ctx = Ctx(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(_repo(tmp_path)),
            "num_seq_per_target": 3,
            "seed": 1,
            "device": "cpu",
            "python_executable": __import__("sys").executable,
        }
    )
    step = ProteinmpnnNativeRecoveryScanStep()
    step.run(ctx, [])
    out = ctx["recovery"]
    assert out.data.shape == (3, 3)
    assert out.dims == ["position", "statistic"]
    assert list(out.labels["position"]) == ["1", "2", "3"]
    assert out.data[:, 0].tolist() == pytest.approx([1.0, 1.0, 1 / 3])
    assert out.info["native_sequence"] == "ACD"
    assert out.info["num_samples"] == 3
    assert step.export(ctx)["length"] == 3


def test_parameter_errors(tmp_path: Path) -> None:
    structure = tmp_path / "complex.pdb"
    structure.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    repo = _repo(tmp_path)
    base = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "num_seq_per_target": 3,
        "python_executable": __import__("sys").executable,
    }
    cases = [
        ({"structure_path": str(tmp_path / "missing.pdb")}, "does not exist"),
        ({"proteinmpnn_path": str(tmp_path)}, "does not contain"),
        ({"model_name": "v_99_999"}, "model_name must be"),
        ({"num_seq_per_target": 1}, "num_seq_per_target"),
        ({"sampling_temp": "0"}, "sampling_temp"),
        ({"seed": -1}, "seed must not be negative"),
        ({"device": "tpu"}, "device must be"),
        ({"weights_path": str(tmp_path / "no-weights")}, "is not a directory"),
    ]
    for overrides, message in cases:
        ctx = Ctx({**base, **overrides})
        with pytest.raises(StepError, match=message):
            ProteinmpnnNativeRecoveryScanStep().run(ctx, [])


def test_runner_failure(tmp_path: Path) -> None:
    structure = tmp_path / "complex.pdb"
    structure.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    repo = tmp_path / "Broken"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.stderr.write('boom')\nsys.exit(4)\n")
    ctx = Ctx(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo),
            "num_seq_per_target": 3,
            "python_executable": __import__("sys").executable,
        }
    )
    with pytest.raises(StepError, match="exit code 4"):
        ProteinmpnnNativeRecoveryScanStep().run(ctx, [])


@pytest.mark.skipif(not REAL_REPO.is_dir(), reason="official ProteinMPNN checkout not available")
def test_official_runner_recovery(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    ctx = Ctx(
        {
            "structure_path": str(fixture),
            "proteinmpnn_path": str(REAL_REPO),
            "num_seq_per_target": 4,
            "seed": 1,
            "device": "cpu",
            "chains": "C",
        }
    )
    ProteinmpnnNativeRecoveryScanStep().run(ctx, [])
    out = ctx["recovery"]
    assert out.data.shape == (16, 3)
    assert 0.0 <= float(out.data[:, 0].mean()) <= 1.0
