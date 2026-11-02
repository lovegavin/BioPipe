"""structure_tm_score: TM-score against the tmtools oracle."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.reader import read_source
from src.task.step.steps.structure_tm_score import ca_map, d0_for_length, match_residues, tm_score

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "vhh_1mel.pdb"


def test_d0_matches_reference_values():
    assert d0_for_length(10) == pytest.approx(0.5)
    assert d0_for_length(100) == pytest.approx(1.24 * (100 - 15) ** (1 / 3) - 1.8, rel=1e-9)


def _ca(sequence_length=20):
    rng = np.random.default_rng(3)
    return rng.normal(0.0, 8.0, (sequence_length, 3))


def test_identical_structures_score_one():
    coordinates = _ca()
    score, rmsd, aligned, d0 = tm_score(coordinates, coordinates)
    assert score == pytest.approx(1.0, rel=1e-6)
    assert rmsd == pytest.approx(0.0, abs=1e-9)
    assert aligned == pytest.approx(1.0)


def test_rotation_and_noise():
    coordinates = _ca()
    angle = np.deg2rad(30.0)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]])
    moved = (rotation @ coordinates.T).T + np.array([5.0, -3.0, 2.0])
    score, rmsd, aligned, d0 = tm_score(moved, coordinates)
    assert score == pytest.approx(1.0, rel=1e-6)
    assert rmsd == pytest.approx(0.0, abs=1e-6)
    noisy = coordinates + np.random.default_rng(5).normal(0.0, 0.35, coordinates.shape)
    score, rmsd, aligned, d0 = tm_score(noisy, coordinates)
    assert 0.5 < score < 1.0
    assert aligned > 0.5


def test_against_tmtools_on_fixture():
    tmtools = pytest.importorskip("tmtools")
    form = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    chain_a = ca_map(form, "field", "A")
    chain_b = ca_map(form, "field", "B")
    first, second, shared = match_residues(chain_a, chain_b)
    ours, rmsd, aligned, d0 = tm_score(first, second)
    result = tmtools.tm_align(first.astype(np.float64), second.astype(np.float64), "A" * len(shared), "A" * len(shared))
    oracle = float(getattr(result, "tm_norm_chain2", getattr(result, "tm_norm_chain1", 0.0)))
    assert abs(ours - oracle) < 0.02, (ours, oracle)
    assert len(shared) > 100


def test_run_matches_contract(tmp_path):
    form = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    run(ctx, [{"name": "structure_tm_score", "inputs": ["pdb"], "params": {"output": "tm", "reference_path": str(FIXTURE), "model_chains": "A", "reference_chains": "B"}}])
    result = ctx["tm"]
    assert result.dims == ["model", "statistic"]
    assert 0.0 <= float(result.data[0, 0]) <= 1.0
    assert result.info["n_residues"] > 100


def test_errors(tmp_path):
    form = read_source(str(FIXTURE), ["atom", "field"], {"atom": "auto", "field": "builtin"})
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = form
    with pytest.raises(StepError, match="is not a file"):
        run(ctx, [{"name": "structure_tm_score", "inputs": ["pdb"], "params": {"output": "tm", "reference_path": str(tmp_path / "nope.pdb")}}])
    shifted = tmp_path / "shifted.pdb"
    shifted_lines = []
    for line in FIXTURE.read_text().splitlines():
        if line.startswith(("ATOM", "HETATM")):
            number = int(line[22:26]) + 1000
            line = line[:22] + f"{number:4d}" + line[26:]
        shifted_lines.append(line)
    shifted.write_text("\n".join(shifted_lines) + "\n")
    with pytest.raises(StepError, match="only"):
        run(ctx, [{"name": "structure_tm_score", "inputs": ["pdb"], "params": {"output": "tm", "reference_path": str(shifted)}}])
