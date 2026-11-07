"""Tests for the ProteinMPNN probability profile operator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps import proteinmpnn_probability_profile as module
from src.task.step.steps.proteinmpnn_probability_profile import (
    AA_ORDER,
    ProteinmpnnProbabilityProfileStep,
    native_codes_to_sequence,
    probabilities,
)

FAKE_RUNNER = '''
import json
import sys
from pathlib import Path

import numpy as np

args = sys.argv[1:]
argv = dict(zip(args[0::2], args[1::2]))
pdb = Path(argv["--pdb_path"])
out = Path(argv["--out_folder"])
folder = out / "conditional_probs_only"
folder.mkdir(parents=True, exist_ok=True)

length = 4
log_p = np.full((1, length, 21), np.log(0.05), dtype=np.float64)
for index in range(length):
    log_p[0, index, index] = np.log(0.9)
log_p[0, 3, :20] = np.log(1.0 / 20.0)
s = np.array([0, 1, 2, 3], dtype=np.int64)
mask = np.array([1.0, 1.0, 1.0, 0.0], dtype=np.float64)
design = np.array([1.0, 1.0, 0.0, 0.0], dtype=np.float64)
np.savez(folder / f"{pdb.stem}.npz", log_p=log_p, S=s, mask=mask, design_mask=design)
# record the invocation for command assertions
Path("captured.json").write_text(
    json.dumps({"argv": args, "cwd": str(Path.cwd()), "cuda": os.environ.get("CUDA_VISIBLE_DEVICES")})
    if False
    else json.dumps({"argv": args, "cwd": str(Path.cwd())}),
    encoding="utf-8",
)
'''


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    (repo / "vanilla_model_weights").mkdir()
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"fake")
    return repo


def _structure(tmp_path: Path) -> Path:
    path = tmp_path / "complex.pdb"
    path.write_text("HEADER    MINI\nATOM      1  CA  ALA A   1       0.000   0.000   0.000\nEND\n", encoding="utf-8")
    return path


def _run(params: dict) -> tuple:
    step = ProteinmpnnProbabilityProfileStep()
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_helpers_probabilities_and_sequence(tmp_path: Path):
    path = tmp_path / "p.npz"
    log_p = np.full((2, 3, 21), np.log(0.05))
    log_p[:, 0, 0] = np.log(1.0)
    np.savez(path, log_p=log_p, S=np.array([0, 1, 2]), mask=np.ones(3), design_mask=np.ones(3))
    mean, native, mask, design = probabilities(path)
    assert mean.shape == (3, 20)
    assert np.isclose(mean[0, 0], 1.0)
    assert np.isclose(mean[1, 5], 0.05)
    assert native.tolist() == [0, 1, 2]
    assert mask.tolist() == [1.0, 1.0, 1.0]
    assert design.tolist() == [1.0, 1.0, 1.0]
    assert native_codes_to_sequence(np.array([0, 4, 30])) == "AF" + "X"


def test_probabilities_validates_shapes(tmp_path: Path):
    path = tmp_path / "bad.npz"
    np.savez(path, log_p=np.zeros((3,)), S=np.array([0]), mask=np.ones(1), design_mask=np.ones(1))
    with pytest.raises(StepError, match="expected \\(batches, positions, alphabet\\)"):
        probabilities(path)
    path2 = tmp_path / "bad2.npz"
    np.savez(path2, log_p=np.zeros((1, 2, 5)), S=np.array([0, 1]), mask=np.ones(2), design_mask=np.ones(2))
    with pytest.raises(StepError, match="fewer than 20 alphabet columns"):
        probabilities(path2)


def test_step_with_fake_runner(tmp_path: Path):
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    out, export = _run(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo),
            "python_executable": sys.executable,
            "device": "cpu",
            "seed": 1,
        }
    )
    assert list(out.dims) == ["position", "amino_acid"]
    # 4 positions but the fourth is masked out.
    assert out.data.shape == (3, 20)
    assert out.labels["position"] == {"1": 0, "2": 1, "3": 2}
    assert out.labels["amino_acid"]["A"] == 0
    assert np.isclose(out.data[0, 0], 0.9)
    assert np.isclose(out.data[1, 1], 0.9)
    assert np.isclose(out.data[2, 2], 0.9)
    assert out.info["native_sequence"] == "ACDE"
    assert out.info["n_positions"] == 3
    assert out.info["design_mask"] == [1.0, 1.0, 0.0]
    assert out.info["most_likely"][:3] == ["A", "C", "D"]
    assert export["n_positions"] == 3
    captured = json.loads((repo / "captured.json").read_text(encoding="utf-8"))
    argv = captured["argv"]
    assert "--conditional_probs_only" in argv
    assert argv[argv.index("--conditional_probs_only") + 1] == "1"
    assert "--num_seq_per_target" in argv
    assert argv[argv.index("--num_seq_per_target") + 1] == "1"
    assert argv[argv.index("--batch_size") + 1] == "1"
    assert captured["cwd"] == str(repo)


def test_step_parameter_errors(tmp_path: Path):
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="structure_path"):
        _run({"structure_path": str(tmp_path / "missing.pdb"), "proteinmpnn_path": str(repo)})
    with pytest.raises(StepError, match="must be a .pdb file"):
        bad = tmp_path / "x.txt"
        bad.write_text("x", encoding="utf-8")
        _run({"structure_path": str(bad), "proteinmpnn_path": str(repo)})
    with pytest.raises(StepError, match="proteinmpnn_path"):
        _run({"structure_path": str(structure), "proteinmpnn_path": str(tmp_path / "none")})
    with pytest.raises(StepError, match="model_name must be one of"):
        _run(
            {
                "structure_path": str(structure),
                "proteinmpnn_path": str(repo),
                "model_name": "v_99_999",
            }
        )
    with pytest.raises(StepError, match="device must be 'cpu' or 'cuda'"):
        _run({"structure_path": str(structure), "proteinmpnn_path": str(repo), "device": "gpu"})
    with pytest.raises(StepError, match="num_batches must be between 1 and 8"):
        _run({"structure_path": str(structure), "proteinmpnn_path": str(repo), "num_batches": 0})


REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")
FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


@pytest.mark.skipif(
    os.environ.get("OPERON_RUN_PROTEINMPNN") != "1"
    or not (REAL_REPO / "protein_mpnn_run.py").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file()
    or not FIXTURE.is_file(),
    reason="official ProteinMPNN checkout/weights or fixture unavailable",
)
def test_official_runner_profile():
    out, export = _run(
        {
            "structure_path": str(FIXTURE),
            "proteinmpnn_path": str(REAL_REPO),
            "weights_path": str(REAL_REPO / "vanilla_model_weights"),
            "python_executable": sys.executable,
            "model_name": "v_48_020",
            "chains": "C",
            "device": "cpu",
            "seed": 1,
        }
    )
    assert out.data.shape == (16, 20)
    assert out.info["native_sequence"] == "SRALRYYYVKNIIKKV"
    row_sums = out.data.sum(axis=1)
    assert np.all(row_sums <= 1.0001)
    assert np.all(out.data >= 0.0)
    assert out.info["n_positions"] == 16
    assert export["model_name"] == "v_48_020"
