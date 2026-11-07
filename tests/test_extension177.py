"""Tests for the LigandMPNN active-site design operator."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.ligandmpnn_active_site_design import (
    LigandmpnnActiveSiteDesignStep,
    active_site,
    fixed_positions,
    ligand_atoms,
    parse_structure,
    protein_residues,
)

FIXTURE = Path(__file__).parent / "fixtures" / "ligand_1bc8_c60_75.pdb"
REAL_REPO = Path("/home/gavin/tools/LigandMPNN")

FAKE_RUNNER = '''"""Fake LigandMPNN runner."""

import json
import sys
from pathlib import Path


def main() -> None:
    argv = sys.argv[1:]
    out = None
    structure = ""
    for index, token in enumerate(argv):
        if token == "--out_folder":
            out = Path(argv[index + 1])
        if token == "--pdb_path":
            structure = argv[index + 1]
    assert out is not None
    out.mkdir(parents=True, exist_ok=True)
    (out / "seqs").mkdir(exist_ok=True)
    stem = Path(structure).stem
    records = [
        ">%s, T=0.1, seed=1" % stem,
        "AAAAAAAAAAAAAAAA",
        ">%s, id=1, T=0.1, seed=1, overall_confidence=0.8, ligand_confidence=0.9, seq_rec=0.5" % stem,
        "WWAALLLL",
        ">%s, id=2, T=0.1, seed=1, overall_confidence=0.6, ligand_confidence=0.7, seq_rec=0.4" % stem,
        "WWAALLLL",
    ]
    (out / "seqs" / (stem + ".fa")).write_text("\\n".join(records) + "\\n", encoding="utf-8")
    Path(str(out / "captured.json")).write_text(
        json.dumps({"argv": argv, "cwd": str(Path.cwd())}), encoding="utf-8"
    )


main()
'''


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path: Path, body: str = FAKE_RUNNER) -> Path:
    repo = tmp_path / "LigandMPNN"
    repo.mkdir()
    (repo / "run.py").write_text(body, encoding="utf-8")
    return repo


def _run(params):
    step = LigandmpnnActiveSiteDesignStep()
    ctx = Ctx({"structure_path": str(FIXTURE), "python_executable": sys.executable, **params})
    step.run(ctx, [])
    return step, ctx


def test_parse_structure_and_ligand() -> None:
    atoms = parse_structure(FIXTURE)
    assert len(atoms) > 60
    ligand = ligand_atoms(atoms, "LIG")
    assert len(ligand) == 3
    assert {atom["resname"] for atom in ligand} == {"LIG"}


def test_active_site_and_fixed_positions() -> None:
    atoms = parse_structure(FIXTURE)
    ligand = ligand_atoms(atoms, "LIG")
    active = active_site(atoms, ligand, 8.0)
    assert active
    residues = protein_residues(atoms)
    fixed = fixed_positions(residues, active)
    active_keys = {
        f"{atom['chain']}{atom['number']}{atom['icode']}".strip() for atom in active
    }
    assert active_keys
    assert active_keys.isdisjoint(fixed)
    assert len(fixed) == len(residues) - len(active_keys)


def test_helper_errors() -> None:
    atoms = parse_structure(FIXTURE)
    with pytest.raises(StepError, match="no ligand heavy atom matches"):
        ligand_atoms(atoms, "XYZ")
    ligand = ligand_atoms(atoms, "LIG")
    for cutoff, message in ((0.0, "cutoff must be in"), (50.0, "cutoff must be in")):
        with pytest.raises(StepError, match=message):
            active_site(atoms, ligand, cutoff)


def test_step_output(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    step, ctx = _run(
        {
            "ligandmpnn_path": str(repo),
            "ligand_resnames": "LIG",
            "cutoff": 8.0,
            "num_seq_per_target": 2,
            "temperature": 0.1,
            "seed": 1,
        }
    )
    out = ctx["out"]
    assert list(out.dims) == ["design", "statistic"]
    assert out.data.shape == (2, 3)
    assert list(out.labels["statistic"]) == [
        "overall_confidence",
        "ligand_confidence",
        "seq_recovery",
    ]
    assert out.data[0, 0] == pytest.approx(0.8)
    assert out.info["n_fixed"] > 0
    assert out.info["active_site_residues"]
    assert out.info["sequences"] == ["WWAALLLL", "WWAALLLL"]
    captured = json.loads(
        (repo / "captured.json").read_text(encoding="utf-8")
    ) if (repo / "captured.json").is_file() else None
    assert captured is None or "--fixed_residues" in captured["argv"]
    if captured is not None:
        assert "--number_of_batches" in captured["argv"]
    exported = step.export(ctx)
    assert exported["n_designs"] == 2


@pytest.mark.parametrize(
    "params, message",
    [
        ({"num_seq_per_target": 0}, "num_seq_per_target"),
        ({"temperature": 0.0}, "temperature"),
        ({"temperature": 6.0}, "temperature"),
        ({"device": "tpu"}, "device must be 'cpu' or 'cuda'"),
    ],
)
def test_parameter_errors(tmp_path: Path, params, message: str) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(StepError, match=message):
        _run({"ligandmpnn_path": str(repo), **params})


def test_missing_structure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(StepError, match="structure_path must point"):
        _run({"ligandmpnn_path": str(repo), "structure_path": str(tmp_path / "none.pdb")})


def test_runner_failure(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "import sys\nsys.stderr.write('boom\\n')\nsys.exit(4)\n")
    with pytest.raises(StepError, match="exit code 4"):
        _run({"ligandmpnn_path": str(repo)})


@pytest.mark.skipif(
    os.environ.get("OPERON_RUN_LIGANDMPNN") != "1"
    or not (REAL_REPO / "run.py").is_file()
    or not (REAL_REPO / "model_params" / "ligandmpnn_v_32_010_25.pt").is_file(),
    reason="official LigandMPNN checkout or weights missing",
)
def test_official_runner_active_site() -> None:
    step, ctx = _run(
        {
            "ligandmpnn_path": str(REAL_REPO),
            "weights_path": str(REAL_REPO / "model_params" / "ligandmpnn_v_32_010_25.pt"),
            "ligand_resnames": "LIG",
            "cutoff": 8.0,
            "num_seq_per_target": 2,
            "temperature": 0.1,
            "seed": 1,
            "timeout": 900,
        }
    )
    out = ctx["out"]
    assert out.data.shape == (2, 3)
    assert out.info["n_fixed"] > 0
    assert np.isfinite(out.data).all()
