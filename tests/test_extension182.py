"""Tests for the ProteinMPNN temperature-ladder operator."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_temperature_ladder import (
    ProteinmpnnTemperatureLadderStep,
    pairwise_identity,
    parse_temperatures,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")

FAKE_RUNNER = r'''
import sys
from pathlib import Path

args = sys.argv[1:]
def value(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default

pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
temperature = value("--sampling_temp", "0.1")
count = int(value("--num_seq_per_target", "2"))
if temperature == "0.1":
    sequences = ["A" * 16 for _ in range(count)]
else:
    sequences = ["A" * 15 + chr(65 + index) for index in range(count)]
lines = []
for index, sequence in enumerate(sequences, start=1):
    lines.append(
        ">T=" + temperature + ", sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=1." + str(index) + ", seq_recovery=0.5"
    )
    lines.append(sequence)
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
(seqs / (pdb.stem + ".fa")).write_text("\n".join(lines) + "\n")
'''


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"x")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    return repo


def _params(repo: Path, **overrides):
    params = {
        "structure_path": str(FIXTURE),
        "proteinmpnn_path": str(repo),
        "temperatures": "0.1,0.3",
        "num_seq_per_target": 3,
        "seed": 1,
        "device": "cpu",
        "output": "ladder",
    }
    params.update(overrides)
    return params


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_parse_temperatures():
    assert parse_temperatures("0.3, 0.1") == [0.1, 0.3]
    assert parse_temperatures("0.1;0.1") == [0.1]
    with pytest.raises(StepError, match="at least one temperature"):
        parse_temperatures("  ")
    with pytest.raises(StepError, match="is not a number"):
        parse_temperatures("hot")
    with pytest.raises(StepError, match="must be in"):
        parse_temperatures("1.5")
    with pytest.raises(StepError, match="at most five"):
        parse_temperatures("0.1,0.2,0.3,0.4,0.5,0.6")


def test_pairwise_identity():
    assert pairwise_identity(["AAAA", "AAAA"]) == pytest.approx(1.0)
    assert pairwise_identity(["AAAA", "AAAG"]) == pytest.approx(0.75)
    assert pairwise_identity(["AAAA"]) == 0.0
    with pytest.raises(StepError, match="different lengths"):
        pairwise_identity(["AAAA", "AAA"])


def test_step_outputs(tmp_path):
    repo = _repo(tmp_path)
    step = ProteinmpnnTemperatureLadderStep()
    form, export = _run(step, _params(repo))
    assert form.data.shape == (2, 4)
    assert list(form.dims) == ["temperature", "statistic"]
    assert list(form.labels["temperature"]) == ["0.1", "0.3"]
    assert list(form.labels["statistic"]) == [
        "mean_score",
        "mean_seq_recovery",
        "diversity",
        "n_designs",
    ]
    assert form.data[0, 2] == pytest.approx(0.0, abs=1e-6)
    assert form.data[1, 2] > 0.0
    assert form.data[1, 0] == pytest.approx(1.2, abs=1e-6)
    assert form.data[:, 3].tolist() == [3.0, 3.0]
    assert export["temperatures"] == [0.1, 0.3]
    assert export["diversity"][0] == pytest.approx(0.0, abs=1e-6)
    assert set(form.info["sequences_per_temperature"]) == {"0.1", "0.3"}


def test_parameter_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_PROTEINMPNN_PATH", raising=False)
    repo = _repo(tmp_path)
    step = ProteinmpnnTemperatureLadderStep()
    with pytest.raises(StepError, match="structure_path is required"):
        _run(step, _params(repo, structure_path=""))
    with pytest.raises(StepError, match="is not a file"):
        _run(step, _params(repo, structure_path=str(tmp_path / "missing.pdb")))
    with pytest.raises(StepError, match="proteinmpnn_path is required"):
        _run(step, _params(repo, proteinmpnn_path=""))
    with pytest.raises(StepError, match="must contain protein_mpnn_run.py"):
        _run(step, _params(repo, proteinmpnn_path=str(tmp_path)))
    with pytest.raises(StepError, match="weights_path"):
        empty = tmp_path / "noweights"
        empty.mkdir()
        (empty / "protein_mpnn_run.py").write_text("raise SystemExit(0)")
        _run(step, _params(empty))
    with pytest.raises(StepError, match="model_name must be one of"):
        _run(step, _params(repo, model_name="v_99_999"))
    with pytest.raises(StepError, match="must be at least 2"):
        _run(step, _params(repo, num_seq_per_target=1))
    with pytest.raises(StepError, match="seed must not be negative"):
        _run(step, _params(repo, seed=-1))
    with pytest.raises(StepError, match="device must be"):
        _run(step, _params(repo, device="tpu"))
    with pytest.raises(StepError, match="timeout must be positive"):
        _run(step, _params(repo, timeout=0))
    with pytest.raises(StepError, match="at least one temperature"):
        _run(step, _params(repo, temperatures=""))


def test_runner_failure(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(5)\n")
    step = ProteinmpnnTemperatureLadderStep()
    with pytest.raises(StepError, match="exit code 5"):
        _run(step, _params(repo))


def test_missing_fasta(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(0)\n")
    step = ProteinmpnnTemperatureLadderStep()
    with pytest.raises(StepError, match="produced no FASTA"):
        _run(step, _params(repo))


@pytest.mark.skipif(
    not REAL_REPO.is_dir()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="official ProteinMPNN checkout is not available",
)
def test_official_temperature_ladder():
    step = ProteinmpnnTemperatureLadderStep()
    form, export = _run(
        step,
        {
            "structure_path": str(FIXTURE),
            "proteinmpnn_path": str(REAL_REPO),
            "temperatures": "0.1,0.4",
            "num_seq_per_target": 3,
            "seed": 1,
            "device": "cpu",
            "chains": "C",
            "output": "ladder",
        },
    )
    assert form.data.shape == (2, 4)
    assert form.data[1, 2] >= form.data[0, 2]
    assert export["n_designs"] == 3
    for group in form.info["sequences_per_temperature"].values():
        assert len(group) == 3
        assert all(len(sequence) == 16 for sequence in group)
