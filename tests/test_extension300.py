"""antifold_design: FASTA/profile parsing and runner contract."""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.antifold_design import (
    antifold_command,
    parse_fasta,
    parse_profile,
    profile_summary,
)

FASTA = """>pdb_AL , score=1.5146, global_score=1.5146, regions=['CDR1', 'CDR2'], model_name=AntiFold, seed=42
DVQLQASGGG
> T=0.20, sample=1, score=0.5436, global_score=1.1799, seq_recovery=0.8571, mutations=37
DVQLQASGGA
> T=0.20, sample=2, score=0.5426, global_score=1.1796, seq_recovery=0.8649, mutations=35
DVQLQAGGGA
"""

PROFILE = """pdb_posins,pdb_chain,pdb_res,top_res,pdb_pos,perplexity,A,C,D,E,F,G,H,I,K,L,M,N,P,Q,R,S,T,V,W,Y
2,A,V,M,2,1.6845,-4.73,-6.71,-6.02,-5.90,-6.23,-4.19,-6.43,-5.55,-6.15,-5.37,-0.09,-6.20,-4.77,-6.05,-5.73,-4.66,-5.25,-4.62,-7.0,-6.4
3,A,Q,Q,3,1.1707,-8.07,-11.89,-8.15,-5.35,-10.82,-7.99,-6.45,-10.79,-4.81,-6.97,-8.55,-6.00,-13.21,-0.02,-5.70,-8.76,-7.42,-5.30,-7.1,-6.3
"""


def _write(tmp_path):
    fasta = tmp_path / "out.fasta"
    fasta.write_text(FASTA)
    profile = tmp_path / "out.csv"
    profile.write_text(PROFILE)
    return fasta, profile


def test_parse_fasta(tmp_path):
    fasta, _ = _write(tmp_path)
    records = parse_fasta(fasta)
    assert len(records) == 3
    assert records[0]["is_wildtype"] and records[0]["score"] == pytest.approx(1.5146)
    assert records[1]["sample"] == 1 and records[1]["mutations"] == 37
    assert records[2]["seq_recovery"] == pytest.approx(0.8649)


def test_parse_profile_and_summary(tmp_path):
    _, profile = _write(tmp_path)
    rows = parse_profile(profile)
    assert len(rows) == 2
    assert rows[0]["wild_type"] == "V" and rows[0]["preferred"] == "M" and rows[0]["is_preferred"]
    assert rows[1]["is_preferred"] is False
    summary = profile_summary(rows)
    assert summary["n_preferred_changes"] == 1
    assert summary["mean_perplexity"] == pytest.approx((1.6845 + 1.1707) / 2, rel=1e-6)


def test_command_contract(tmp_path):
    command = antifold_command(
        Path("/tmp/x.pdb"),
        tmp_path,
        python_executable=sys.executable,
        nanobody_chain="A",
        antigen_chain="L",
        num_seq_per_target=3,
        sampling_temp="0.3",
    )
    assert command[:3] == [sys.executable, "-m", "antifold.main"]
    assert command[command.index("--nanobody_chain") + 1] == "A"
    assert command[command.index("--num_seq_per_target") + 1] == "3"


RUNNER = """import shutil, sys, json
from pathlib import Path
out = Path(sys.argv[sys.argv.index("--out_dir") + 1])
out.mkdir(parents=True, exist_ok=True)
json.dump(sys.argv, open(out / "argv.json", "w"))
here = Path(__file__).resolve().parent
shutil.copyfile(here / "expected.fasta", out / "design.fasta")
shutil.copyfile(here / "expected.csv", out / "design.csv")
"""


def _params(tmp_path, script):
    pdb = tmp_path / "input.pdb"
    pdb.write_text("ATOM\n")
    return {
        "output": "designs",
        "structure_path": str(pdb),
        "nanobody_chain": "A",
        "antigen_chain": "L",
        "num_seq_per_target": 2,
        "sampling_temp": "0.2",
        "python_executable": sys.executable,
        "runner_path": str(script),
    }, pdb


def test_run_matches_contract(tmp_path):
    script = tmp_path / "fake_antifold.py"
    script.write_text(RUNNER)
    (tmp_path / "expected.fasta").write_text(FASTA)
    (tmp_path / "expected.csv").write_text(PROFILE)
    params, _ = _params(tmp_path, script)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "antifold_design", "params": params}])
    result = ctx["designs"]
    assert result.dims == ["design", "statistic"]
    assert result.data.shape == (2, 4)
    assert result.labels["design"] == {"design1": 0, "design2": 1}
    assert result.info["wild_type_sequence"] == "DVQLQASGGG"
    assert result.info["profile_summary"]["n_preferred_changes"] == 1


def test_errors(tmp_path):
    script = tmp_path / "fake_antifold.py"
    script.write_text(RUNNER)
    (tmp_path / "expected.fasta").write_text(FASTA)
    (tmp_path / "expected.csv").write_text(PROFILE)
    params, pdb = _params(tmp_path, script)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    with pytest.raises(StepError, match="not a file"):
        run(ctx, [{"name": "antifold_design", "params": {**params, "structure_path": str(tmp_path / "nope.pdb")}}])
    bad = tmp_path / "input.txt"
    bad.write_text("x")
    with pytest.raises(StepError, match="must be a .pdb"):
        run(ctx, [{"name": "antifold_design", "params": {**params, "structure_path": str(bad)}}])
    with pytest.raises(StepError, match="at least one antibody chain"):
        run(ctx, [{"name": "antifold_design", "params": {**params, "nanobody_chain": ""}}])
    missing = tmp_path / "does_not_exist.py"
    with pytest.raises(StepError, match="failed with exit code"):
        run(ctx, [{"name": "antifold_design", "params": {**params, "runner_path": str(missing)}}])


@pytest.mark.skipif(os.environ.get("OPERON_ANTIFOLD_REAL") != "1", reason="set OPERON_ANTIFOLD_REAL=1 to run AntiFold")
def test_real_antifold(tmp_path):
    pytest.importorskip("antifold")
    fixture = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "antifold_design", "params": {"output": "designs", "structure_path": str(fixture), "nanobody_chain": "A", "antigen_chain": "L", "num_seq_per_target": 2, "sampling_temp": "0.2"}}])
    result = ctx["designs"]
    assert result.data.shape[0] == 2
    assert result.info["wild_type_score"] > 0
    assert result.info["profile_summary"]["n_residues"] > 100
    assert all(0.0 <= value <= 1.0 for value in result.data[:, 2])
