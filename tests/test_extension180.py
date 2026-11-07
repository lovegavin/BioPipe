"""Tests for the multi-checkpoint ProteinMPNN consensus operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_multi_model_consensus import (
    AA_ORDER,
    ProteinmpnnMultiModelConsensusStep,
    consensus_sequence,
    parse_models,
    position_frequencies,
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
model = value("--model_name")
count = int(value("--num_seq_per_target", "2"))
second = "A" if model.endswith("002") else "W"
lines = []
for index in range(1, count + 1):
    lines.append(
        ">T=0.1, sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=1." + str(index) + ", seq_recovery=0.5"
    )
    lines.append("S" * 15 + second)
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
        "models": "v_48_002,v_48_020",
        "num_seq_per_target": 2,
        "seed": 1,
        "device": "cpu",
        "output": "consensus",
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


def test_parse_models():
    assert parse_models("v_48_002, v_48_020") == ["v_48_002", "v_48_020"]
    assert parse_models("v_48_020;v_48_010") == ["v_48_020", "v_48_010"]
    with pytest.raises(StepError, match="at least one checkpoint"):
        parse_models("  ")
    with pytest.raises(StepError, match="is unknown"):
        parse_models("v_99_999")
    with pytest.raises(StepError, match="listed twice"):
        parse_models("v_48_002,v_48_002")


def test_position_frequencies_and_consensus():
    frequencies = position_frequencies(["ACD", "ACD", "ACW"], 3)
    assert frequencies.shape == (3, 20)
    for row in frequencies:
        assert pytest.approx(float(row.sum()), abs=1e-6) == 1.0
    a_column = AA_ORDER.index("A")
    d_column = AA_ORDER.index("D")
    w_column = AA_ORDER.index("W")
    assert frequencies[0, a_column] == pytest.approx(1.0)
    assert frequencies[2, d_column] == pytest.approx(2 / 3)
    assert frequencies[2, w_column] == pytest.approx(1 / 3)
    assert consensus_sequence(frequencies) == "ACD"


def test_frequency_errors():
    with pytest.raises(StepError, match="at least one design"):
        position_frequencies([], 3)
    with pytest.raises(StepError, match="does not match the backbone length"):
        position_frequencies(["AC"], 3)
    with pytest.raises(StepError, match="non-standard residue"):
        position_frequencies(["ACX"], 3)


def test_step_outputs_per_model(tmp_path):
    repo = _repo(tmp_path)
    step = ProteinmpnnMultiModelConsensusStep()
    form, export = _run(step, _params(repo))
    assert form.data.shape == (16, 20)
    assert list(form.dims) == ["position", "amino_acid"]
    assert list(form.labels["amino_acid"]) == list(AA_ORDER)
    assert list(form.labels["position"])[:3] == ["1", "2", "3"]
    assert form.info["n_designs"] == 4
    assert form.info["n_models"] == 2
    assert set(form.info["sequences_per_model"]) == {"v_48_002", "v_48_020"}
    assert len(form.info["sequences_per_model"]["v_48_002"]) == 2
    assert form.info["consensus"][:15] == "S" * 15
    assert form.info["consensus"][15] in "AW"
    assert export["models"] == ["v_48_002", "v_48_020"]
    assert export["n_designs"] == 4
    for row in form.data:
        assert pytest.approx(float(row.sum()), abs=1e-6) == 1.0


def test_parameter_errors(tmp_path, monkeypatch):
    monkeypatch.delenv("OPERON_PROTEINMPNN_PATH", raising=False)
    repo = _repo(tmp_path)
    step = ProteinmpnnMultiModelConsensusStep()
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
    with pytest.raises(StepError, match="num_seq_per_target must be positive"):
        _run(step, _params(repo, num_seq_per_target=0))
    with pytest.raises(StepError, match="seed must not be negative"):
        _run(step, _params(repo, seed=-1))
    with pytest.raises(StepError, match="device must be"):
        _run(step, _params(repo, device="tpu"))
    with pytest.raises(StepError, match="timeout must be positive"):
        _run(step, _params(repo, timeout=0))
    with pytest.raises(StepError, match="must differ"):
        _run(step, _params(repo, position_dim="x", amino_acid_dim="x"))


def test_runner_failure(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(4)\n")
    step = ProteinmpnnMultiModelConsensusStep()
    with pytest.raises(StepError, match="exit code 4"):
        _run(step, _params(repo))


def test_missing_fasta(tmp_path):
    repo = _repo(tmp_path)
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.exit(0)\n")
    step = ProteinmpnnMultiModelConsensusStep()
    with pytest.raises(StepError, match="produced no FASTA"):
        _run(step, _params(repo))


@pytest.mark.skipif(
    not REAL_REPO.is_dir()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_002.pt").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="official ProteinMPNN checkpoints are not available",
)
def test_official_two_models():
    step = ProteinmpnnMultiModelConsensusStep()
    form, export = _run(
        step,
        {
            "structure_path": str(FIXTURE),
            "proteinmpnn_path": str(REAL_REPO),
            "models": "v_48_002,v_48_020",
            "num_seq_per_target": 2,
            "seed": 1,
            "device": "cpu",
            "chains": "C",
            "output": "consensus",
        },
    )
    assert form.data.shape == (16, 20)
    assert export["n_designs"] == 4
    assert all(len(group) == 2 for group in form.info["sequences_per_model"].values())
    assert len(form.info["consensus"]) == 16
