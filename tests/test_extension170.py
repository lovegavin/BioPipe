"""Tests for the ProteinMPNN per-position amino-acid profile."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.proteinmpnn_design_profile import (
    ProteinmpnnDesignProfileStep,
    amino_acid_profile,
    profile_matrix,
)
from src.task.step.steps.proteinmpnn_position_entropy import AA_ORDER

REAL_REPO = Path(os.environ.get("OPERON_PROTEINMPNN_PATH", "/home/gavin/tools/ProteinMPNN"))

FAKE_RUNNER = r'''
import json
import sys
from pathlib import Path

argv = sys.argv[1:]
out = Path(argv[argv.index("--out_folder") + 1])
pdb = Path(argv[argv.index("--pdb_path") + 1])
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
generated = [
    "ACDEFG",
    "ACDEFY",
    "ACDEAA",
    "ACDEFG",
]
header = f">{pdb.stem}, T=0.10, seed=1, num_res=6, num_ligand_res=0"
lines = [header, "ACDEFG"]
for index, sequence in enumerate(generated, start=1):
    lines.append(f">{pdb.stem}, id={index}, T=0.10, sample={index}, score=1.0, global_score=1.0, seq_recovery=0.5")
    lines.append(sequence)
(seqs / f"{pdb.stem}.fa").write_text("\n".join(lines) + "\n", encoding="utf-8")
(out / "captured.json").write_text(json.dumps({"argv": argv, "cwd": str(Path.cwd())}), encoding="utf-8")
'''


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    (repo / "vanilla_model_weights").mkdir(parents=True)
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("fake", encoding="utf-8")
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER, encoding="utf-8")
    return repo


def _structure(tmp_path: Path) -> Path:
    path = tmp_path / "mini.pdb"
    path.write_text("ATOM\n", encoding="utf-8")
    return path


def _base(repo: Path, structure: Path) -> dict:
    return {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "weights_path": str(repo / "vanilla_model_weights"),
        "num_seq_per_target": 4,
        "sampling_temp": "0.1",
        "seed": 1,
        "model_name": "v_48_020",
        "device": "cpu",
        "timeout": 120,
        "python_executable": sys.executable,
    }


def test_amino_acid_profile_hand_values() -> None:
    designs = ["ACDEFG", "ACDEFY", "ACDEAA", "ACDEFG"]
    rows = amino_acid_profile(designs, "ACDEFG")
    assert [row["position"] for row in rows] == [1, 2, 3, 4, 5, 6]
    assert [row["consensus"] for row in rows] == ["A", "C", "D", "E", "F", "G"]
    matrix = profile_matrix(rows)
    assert matrix.shape == (6, 20)
    assert np.allclose(matrix[:, AA_ORDER.index("A")], [1.0, 0.0, 0.0, 0.0, 0.25, 0.25])
    assert np.allclose(matrix[:, AA_ORDER.index("Y")], [0.0, 0.0, 0.0, 0.0, 0.0, 0.25])
    assert rows[5]["recovery"] == pytest.approx(0.5)
    assert rows[0]["n_observed"] == 4


def test_profile_errors() -> None:
    with pytest.raises(StepError, match="no designs"):
        amino_acid_profile([], "ACDE")
    with pytest.raises(StepError, match="match the native length"):
        amino_acid_profile(["ACD"], "ACDE")
    with pytest.raises(StepError, match="not a standard amino acid"):
        amino_acid_profile(["ACDX"], "ACDE")


def test_step_writes_matrix(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    step = ProteinmpnnDesignProfileStep()
    ctx = Ctx(_base(repo, structure))
    step.run(ctx, [])
    form = ctx["out"]
    assert isinstance(form, Form)
    assert form.dims == ["position", "amino_acid"]
    assert form.data.shape == (6, 20)
    assert form.labels["amino_acid"]["A"] == 0
    assert form.labels["position"]["1"] == 0
    assert form.info["native_sequence"] == "ACDEFG"
    assert form.info["consensus"] == list("ACDEFG")
    assert form.info["num_samples"] == 4
    assert form.info["aa_order"] == AA_ORDER
    export = step.export(ctx)
    assert export["positions"] == 6
    assert export["num_samples"] == 4
    assert export["consensus"] == "ACDEFG"


def test_step_parameter_errors(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    with pytest.raises(StepError, match="structure_path"):
        ProteinmpnnDesignProfileStep().run(Ctx(_base(repo, tmp_path / "missing.pdb")), [])
    with pytest.raises(StepError, match="protein_mpnn_run.py"):
        ProteinmpnnDesignProfileStep().run(Ctx(_base(tmp_path / "empty", structure)), [])
    bad = _base(repo, structure)
    bad["model_name"] = "v_99_999"
    with pytest.raises(StepError, match="model_name"):
        ProteinmpnnDesignProfileStep().run(Ctx(bad), [])
    bad = _base(repo, structure)
    bad["num_seq_per_target"] = 1
    with pytest.raises(StepError, match="num_seq_per_target"):
        ProteinmpnnDesignProfileStep().run(Ctx(bad), [])
    bad = _base(repo, structure)
    bad["sampling_temp"] = "0"
    with pytest.raises(StepError, match="sampling_temp"):
        ProteinmpnnDesignProfileStep().run(Ctx(bad), [])
    bad = _base(repo, structure)
    bad["device"] = "tpu"
    with pytest.raises(StepError, match="device"):
        ProteinmpnnDesignProfileStep().run(Ctx(bad), [])
    bad = _base(repo, structure)
    bad["amino_acid_dim"] = "position"
    with pytest.raises(StepError, match="must differ"):
        ProteinmpnnDesignProfileStep().run(Ctx(bad), [])


def test_designer_failure_is_reported(tmp_path: Path) -> None:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(
        "import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n", encoding="utf-8"
    )
    (repo / "vanilla_model_weights").mkdir()
    (repo / "vanilla_model_weights" / "v_48_020.pt").write_text("x", encoding="utf-8")
    structure = _structure(tmp_path)
    params = _base(repo, structure)
    params.pop("weights_path")
    with pytest.raises(StepError, match="exit code 3"):
        ProteinmpnnDesignProfileStep().run(Ctx(params), [])


@pytest.mark.skipif(
    not (REAL_REPO / "protein_mpnn_run.py").is_file()
    or not (REAL_REPO / "vanilla_model_weights" / "v_48_020.pt").is_file(),
    reason="official ProteinMPNN checkout with weights is not available",
)
def test_real_designer(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
    params = _base(REAL_REPO, fixture)
    params["num_seq_per_target"] = 2
    step = ProteinmpnnDesignProfileStep()
    ctx = Ctx(params)
    step.run(ctx, [])
    form = ctx["out"]
    assert form.data.shape == (16, 20)
    assert np.allclose(form.data.sum(axis=1), 1.0, atol=1e-6)
    assert form.info["native_sequence"] == "SRALRYYYVKNIIKKV"
