"""Tests for the ProteinMPNN interface redesign operator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_interface_redesign import (
    ProteinmpnnInterfaceRedesignStep,
    fixed_payload,
    interface_residues,
    protein_residues,
    _read_atoms,
)

REAL_REPO = Path("/home/gavin/tools/ProteinMPNN")

FAKE_RUNNER = r'''
import json
import sys
from pathlib import Path

args = sys.argv[1:]
def value(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default

pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
fixed_path = value("--fixed_positions_jsonl")
fixed = json.loads(Path(fixed_path).read_text()) if fixed_path else {}
count = int(value("--num_seq_per_target", "2"))

atom = "ATOM  {serial:>5} {name:<4}ALA A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C"
lines = []
for index in range(1, count + 1):
    lines.append(
        ">T=0.1, sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=1." + str(index) + ", seq_recovery=0.5"
    )
    lines.append("ACDEFG")
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
(seqs / (pdb.stem + ".fa")).write_text("\n".join(lines) + "\n")
(pdb.parent / "captured.json").write_text(
    json.dumps({"fixed": fixed, "chains": value("--pdb_path_chains"), "seed": value("--seed")})
)
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "designs", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element="C"):
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2}"
    )


def _complex(path: Path) -> Path:
    lines = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "GLY", "A", 2, 4.0, 0.0, 0.0),
        _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 2.0),
        _atom(4, "CA", "THR", "B", 2, 30.0, 30.0, 30.0),
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def _repo(root: Path) -> Path:
    repo = root / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True, exist_ok=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    return repo


def _params(tmp_path: Path, **overrides) -> dict:
    repo = _repo(tmp_path)
    base = {
        "structure_path": str(_complex(tmp_path / "complex.pdb")),
        "proteinmpnn_path": str(repo),
        "binder_chains": "A",
        "target_chains": "B",
        "cutoff": 8.0,
        "num_seq_per_target": 2,
        "seed": 1,
        "device": "cpu",
        "python_executable": __import__("sys").executable,
    }
    base.update(overrides)
    return base


def test_structure_helpers(tmp_path: Path) -> None:
    atoms = _read_atoms(_complex(tmp_path / "complex.pdb"))
    residues = protein_residues(atoms)
    assert sorted(residues) == ["A:ALA:1", "A:GLY:2", "B:SER:1", "B:THR:2"]
    assert interface_residues(residues, ["A"], ["B"], 8.0) == ["A:ALA:1", "A:GLY:2"]
    assert interface_residues(residues, ["A"], ["B"], 3.0) == ["A:ALA:1"]
    with pytest.raises(StepError, match="within"):
        interface_residues(residues, ["A"], ["B"], 1.0)


def test_fixed_payload_is_sequential(tmp_path: Path) -> None:
    atoms = _read_atoms(_complex(tmp_path / "complex.pdb"))
    residues = protein_residues(atoms)
    payload = fixed_payload("complex", residues, {"A:ALA:1"})
    assert payload == {"complex": {"A": [2], "B": [1, 2]}}


def test_step_writes_interface_designs(tmp_path: Path) -> None:
    params = _params(tmp_path)
    ctx = Ctx(params)
    step = ProteinmpnnInterfaceRedesignStep()
    step.run(ctx, [])
    out = ctx["designs"]
    assert out.data.shape == (2, 3)
    assert out.dims == ["design", "statistic"]
    assert list(out.labels["statistic"]) == ["score", "global_score", "seq_recovery"]
    assert out.info["interface_residues"] == ["A:ALA:1", "A:GLY:2"]
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert captured["chains"] == "A"
    assert captured["seed"] == "1"
    assert captured["fixed"] == {"complex": {"A": [], "B": [1, 2]}}
    assert step.export(ctx)["n_designs"] == 2


def test_parameter_errors(tmp_path: Path) -> None:
    cases = [
        ({"structure_path": str(tmp_path / "missing.pdb")}, "does not exist"),
        ({"proteinmpnn_path": str(tmp_path)}, "does not contain"),
        ({"model_name": "v_99_999"}, "model_name must be"),
        ({"num_seq_per_target": 0}, "num_seq_per_target"),
        ({"sampling_temp": "0"}, "sampling_temp"),
        ({"seed": -1}, "seed"),
        ({"device": "tpu"}, "device"),
        ({"cutoff": 0.0}, "cutoff"),
        ({"binder_chains": ""}, "binder_chains"),
        ({"target_chains": "A"}, "cannot be both"),
        ({"target_chains": "Z"}, "not found"),
    ]
    for overrides, message in cases:
        ctx = Ctx(_params(tmp_path, **overrides))
        with pytest.raises(StepError, match=message):
            ProteinmpnnInterfaceRedesignStep().run(ctx, [])


def test_runner_failure(tmp_path: Path) -> None:
    repo = tmp_path / "Broken"
    (repo / "vanilla_model_weights").mkdir(parents=True, exist_ok=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("stub")
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.stderr.write('boom')\nsys.exit(3)\n")
    ctx = Ctx(_params(tmp_path, proteinmpnn_path=str(repo)))
    with pytest.raises(StepError, match="exit code 3"):
        ProteinmpnnInterfaceRedesignStep().run(ctx, [])


@pytest.mark.skipif(not REAL_REPO.is_dir(), reason="official ProteinMPNN checkout not available")
def test_official_runner_on_vhh(tmp_path: Path) -> None:
    vhh = Path(__file__).parent / "fixtures" / "vhh_1mel.pdb"
    ctx = Ctx(
        {
            "structure_path": str(vhh),
            "proteinmpnn_path": str(REAL_REPO),
            "binder_chains": "A",
            "target_chains": "",
            "cutoff": 8.0,
            "num_seq_per_target": 1,
            "seed": 1,
            "device": "cpu",
        }
    )
    ProteinmpnnInterfaceRedesignStep().run(ctx, [])
    out = ctx["designs"]
    assert out.data.shape == (1, 3)
    assert out.info["n_interface"] >= 1
    assert np.all(np.isfinite(out.data))
