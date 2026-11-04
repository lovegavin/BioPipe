from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_perplexity import (
    ProteinmpnnPerplexityStep,
    most_likely,
    parse_native,
    perplexity_rows,
    probability_matrix,
)

REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params):
    step = ProteinmpnnPerplexityStep()
    step.run(Ctx(params), [])
    return step


FAKE_RUNNER = r'''import json, sys
from pathlib import Path
import numpy as np
args = sys.argv[1:]
def value(flag):
    return args[args.index(flag) + 1]
pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
sequence = "AC"
tokens = np.asarray([0, 1], dtype=np.int64)
payload = np.full((1, len(sequence), 21), -20.0)
payload[0, 0, :20] = np.log(1.0 / 20.0)
payload[0, 1, :20] = -20.0
payload[0, 1, 0] = 0.0
folder = out / "conditional_probs_only"
folder.mkdir(parents=True, exist_ok=True)
np.savez(
    folder / (pdb.stem + ".npz"),
    log_p=payload,
    S=tokens,
    mask=np.ones(len(sequence)),
    design_mask=np.ones(len(sequence)),
)
Path(pdb.parent / "captured.json").write_text(json.dumps({"argv": args, "cwd": str(Path.cwd())}))
'''


def _repo(tmp_path: Path, failing: bool = False) -> tuple[Path, Path]:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir(parents=True)
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"stub")
    script = repo / "protein_mpnn_run.py"
    if failing:
        script.write_text("import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n")
    else:
        script.write_text(FAKE_RUNNER)
    structure = tmp_path / "complex.pdb"
    structure.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
    )
    return repo, structure


def _parameters(repo: Path, structure: Path, **overrides) -> dict:
    params = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "weights_path": str(repo / "vanilla_model_weights"),
        "python_executable": sys.executable,
        "num_seq_per_target": 1,
        "seed": 1,
        "device": "cpu",
        "timeout": 120,
    }
    params.update(overrides)
    return params


def test_parse_native_reads_first_record(tmp_path: Path) -> None:
    path = tmp_path / "native.fa"
    path.write_text(">native\nACD/EF\n>design\nAAAA\n")
    assert parse_native(path) == "ACDEF"
    (tmp_path / "empty.fa").write_text("")
    with pytest.raises(StepError, match="has no sequence"):
        parse_native(tmp_path / "empty.fa")
    with pytest.raises(StepError, match="is missing"):
        parse_native(tmp_path / "absent.fa")


def test_probability_matrix_normalises_and_trims() -> None:
    payload = {"log_p": np.zeros((1, 3, 21))}
    probabilities = probability_matrix(payload, 2)
    assert probabilities.shape == (2, 20)
    assert np.allclose(probabilities.sum(axis=1), 1.0)


def test_perplexity_rows_hand_values() -> None:
    probabilities = np.full((2, 20), 1.0 / 20.0)
    probabilities[1] = 0.0
    probabilities[1, 0] = 1.0
    rows = perplexity_rows(probabilities)
    assert rows[0][0] == pytest.approx(20.0, rel=1e-9)
    assert rows[0][1] == pytest.approx(np.log2(20.0), rel=1e-9)
    assert rows[0][2] == pytest.approx(0.05, rel=1e-9)
    assert rows[1][0] == pytest.approx(1.0, rel=1e-9)
    assert rows[1][1] == pytest.approx(0.0, abs=1e-12)
    assert rows[1][2] == pytest.approx(1.0, rel=1e-9)
    assert most_likely(probabilities) == "AA"


def test_step_output_and_command(tmp_path: Path) -> None:
    repo, structure = _repo(tmp_path)
    step = _run(_parameters(repo, structure))
    form = step._export_data
    assert form["num_positions"] == 2
    assert form["native_sequence"] == "AC"
    assert form["mean_perplexity"] == pytest.approx(10.5, rel=1e-5)
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert "--conditional_probs_only" in captured["argv"]
    assert captured["cwd"] == str(repo)


def test_parameter_errors(tmp_path: Path) -> None:
    repo, structure = _repo(tmp_path)
    with pytest.raises(StepError, match="not a file"):
        _run(_parameters(repo, structure, structure_path=str(tmp_path / "missing.pdb")))
    with pytest.raises(StepError, match="model_name"):
        _run(_parameters(repo, structure, model_name="v_99"))
    with pytest.raises(StepError, match="num_seq_per_target"):
        _run(_parameters(repo, structure, num_seq_per_target=0))
    with pytest.raises(StepError, match="seed"):
        _run(_parameters(repo, structure, seed=-1))
    with pytest.raises(StepError, match="device"):
        _run(_parameters(repo, structure, device="tpu"))
    with pytest.raises(StepError, match="weights_path"):
        _run(_parameters(repo, structure, weights_path=str(tmp_path / "missing.pt")))


def test_runner_failure_reports_exit_code(tmp_path: Path) -> None:
    repo, structure = _repo(tmp_path, failing=True)
    with pytest.raises(StepError, match="exit code 3"):
        _run(_parameters(repo, structure))


@pytest.mark.skipif(
    not (REAL_REPO / "protein_mpnn_run.py").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="the official ProteinMPNN checkout and weights are required",
)
def test_official_runner_perplexity(tmp_path: Path) -> None:
    structure = Path("/home/gavin/BioPipe/tests/fixtures/backbone_1bc8_c60_75.pdb")
    if not structure.is_file():
        pytest.skip("fixture is missing")
    step = _run(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(REAL_REPO),
            "num_seq_per_target": 1,
            "seed": 1,
            "chains": "C",
            "device": "cpu",
            "timeout": 600,
        }
    )
    assert step._export_data["num_positions"] == 16
    assert step._export_data["native_sequence"] == "SRALRYYYVKNIIKKV"
