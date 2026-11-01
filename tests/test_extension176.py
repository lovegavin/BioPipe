"""Tests for the ProteinMPNN bias-scan operator."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._esm_common import AA_ORDER
from src.task.step.steps.proteinmpnn_bias_scan import (
    ProteinmpnnBiasScanStep,
    bias_shift,
    frequency_matrix,
    parse_bias,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")

FAKE_RUNNER = '''"""Fake ProteinMPNN runner."""

import json
import sys
from pathlib import Path


def main() -> None:
    argv = sys.argv[1:]
    bias = {}
    for index, token in enumerate(argv):
        if token == "--bias_AA_jsonl":
            bias = json.loads(Path(argv[index + 1]).read_text(encoding="utf-8"))
    out = None
    structure = ""
    count = 1
    for index, token in enumerate(argv):
        if token == "--out_folder":
            out = Path(argv[index + 1])
        if token == "--pdb_path":
            structure = argv[index + 1]
        if token == "--num_seq_per_target":
            count = int(argv[index + 1])
    assert out is not None
    out.mkdir(parents=True, exist_ok=True)
    (out / "seqs").mkdir(exist_ok=True)
    stem = Path(structure).stem
    records = [">%s, score=1.0, global_score=1.0, seq_recovery=0.5" % stem]
    residue = "W" if bias.get("W", 0) > 0 else "A"
    for index in range(count):
        records.append(
            ">%s, sample=%d, score=1.0, global_score=1.0, seq_recovery=0.5"
            % (stem, index + 1)
        )
        records.append(residue * 10)
    (out / "seqs" / (stem + ".fa")).write_text("\\n".join(records) + "\\n", encoding="utf-8")
    Path(structure).with_suffix(".json").write_text(
        json.dumps({"bias": bias, "count": count}), encoding="utf-8"
    )


main()
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path: Path, body: str = FAKE_RUNNER) -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_bytes(b"fake")
    (repo / "protein_mpnn_run.py").write_text(body, encoding="utf-8")
    return repo


def _run(params):
    step = ProteinmpnnBiasScanStep()
    ctx = Ctx({"structure_path": str(FIXTURE), **params})
    step.run(ctx, [])
    return step, ctx


def test_parse_bias_variants() -> None:
    assert parse_bias("W:1.5, C:-0.5") == {"W": 1.5, "C": -0.5}
    assert parse_bias("A=2;D=0") == {"A": 2.0, "D": 0.0}


@pytest.mark.parametrize(
    "text, message",
    [
        ("", "at least one amino acid"),
        ("W", "not of the form"),
        ("B:1.0", "single standard amino acid"),
        ("W:high", "not a number"),
        ("W:20", "within"),
    ],
)
def test_parse_bias_errors(text: str, message: str) -> None:
    with pytest.raises(StepError, match=message):
        parse_bias(text)


def test_frequency_and_shift_hand_values() -> None:
    baseline = frequency_matrix([{"sequence": "AA"}, {"sequence": "AA"}], 2)
    biased = frequency_matrix([{"sequence": "WW"}, {"sequence": "AW"}], 2)
    assert baseline[0, AA_ORDER.index("A")] == pytest.approx(1.0)
    shift = bias_shift(baseline, biased)
    # designs are "WW" and "AW": position 1 is W in both, position 2 mixes A and W.
    assert shift[0, AA_ORDER.index("W")] == pytest.approx(0.5)
    assert shift[0, AA_ORDER.index("A")] == pytest.approx(-0.5)
    assert shift[1, AA_ORDER.index("W")] == pytest.approx(1.0)


def test_step_output(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    step, ctx = _run(
        {
            "proteinmpnn_path": str(repo),
            "bias": "W:2.0",
            "num_seq_per_target": 4,
            "temperature": 0.5,
            "seed": 2,
        }
    )
    out = ctx["out"]
    assert list(out.dims) == ["position", "amino_acid"]
    assert out.data.shape == (10, 20)
    assert list(out.labels["amino_acid"])[:3] == ["A", "C", "D"]
    assert out.info["bias"] == {"W": 2.0}
    assert out.info["n_baseline"] == 4
    assert out.info["n_biased"] == 4
    assert out.info["mean_abs_shift"] > 0
    assert out.data[:, AA_ORDER.index("W")].mean() > 0
    assert out.data[:, AA_ORDER.index("A")].mean() < 0
    assert out.info["top_changes"][0]["position"] == 1
    exported = step.export(ctx)
    assert exported["max_shift"] > 0


def test_runner_failure(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        "import sys\nsys.stderr.write('boom\\n')\nsys.exit(3)\n",
    )
    with pytest.raises(StepError, match="exit code 3"):
        _run({"proteinmpnn_path": str(repo), "bias": "W:1.0"})


@pytest.mark.parametrize(
    "params, message",
    [
        ({"bias": ""}, "at least one amino acid"),
        ({"model_name": "v_99_999"}, "model_name must be one of"),
        ({"num_seq_per_target": 1}, "num_seq_per_target"),
        ({"temperature": 0.0}, "temperature"),
        ({"seed": -1}, "seed must not be negative"),
        ({"device": "tpu"}, "device must be 'cpu' or 'cuda'"),
    ],
)
def test_parameter_errors(tmp_path: Path, params, message: str) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(StepError, match=message):
        _run({"proteinmpnn_path": str(repo), **params})


def test_missing_structure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(StepError, match="structure_path must point"):
        _run({"proteinmpnn_path": str(repo), "structure_path": str(tmp_path / "none.pdb")})


@pytest.mark.skipif(
    os.environ.get("BIOPIPE_RUN_PROTEINMPNN") != "1"
    or not (REAL_REPO / "protein_mpnn_run.py").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="official ProteinMPNN checkout or weights missing",
)
def test_official_runner_bias_shift() -> None:
    step, ctx = _run(
        {
            "proteinmpnn_path": str(REAL_REPO),
            "bias": "W:3.0",
            "num_seq_per_target": 24,
            "temperature": 0.5,
            "seed": 3,
            "chain": "C",
            "timeout": 600,
        }
    )
    out = ctx["out"]
    index = AA_ORDER.index("W")
    assert out.data.shape[1] == 20
    assert out.data[:, index].sum() >= 0
    assert out.info["n_baseline"] == out.info["n_biased"] == 24
