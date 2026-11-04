"""Tests for the masked ProteinMPNN design operator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_masked_design import (
    ProteinmpnnMaskedDesignStep,
    mask_payload,
)

FAKE_RUNNER = r'''
import json
import sys
from pathlib import Path

args = sys.argv[1:]
def value(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default

pdb = Path(value("--pdb_path"))
out = Path(value("--out_folder"))
fixed = json.loads(Path(value("--fixed_positions_jsonl")).read_text())
count = int(value("--num_seq_per_target", "2"))
lines = []
for index in range(1, count + 1):
    lines.append(
        ">T=0.1, sample=" + str(index) + ", score=1." + str(index)
        + ", global_score=2." + str(index) + ", seq_recovery=0.5"
    )
    lines.append("ACDEFG")
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
(seqs / (pdb.stem + ".fa")).write_text("\n".join(lines) + "\n")
(pdb.parent / "captured.json").write_text(json.dumps({"fixed": fixed, "chains": value("--pdb_path_chains"), "weights": value("--path_to_model_weights")}))
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
        _atom(3, "CA", "SER", "A", 3, 8.0, 0.0, 0.0),
        _atom(4, "CA", "THR", "B", 1, 0.0, 0.0, 2.0),
        _atom(5, "CA", "VAL", "B", 2, 0.0, 0.0, 4.0),
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def _repo(root: Path) -> Path:
    repo = root / "ProteinMPNN"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    weights = repo / "vanilla_model_weights"
    weights.mkdir(exist_ok=True)
    (weights / "v_48_020.pt").write_text("stub")
    return repo


def _params(tmp_path: Path, **overrides) -> dict:
    repo = _repo(tmp_path)
    base = {
        "structure_path": str(_complex(tmp_path / "complex.pdb")),
        "mask": "A:2",
        "proteinmpnn_path": str(repo),
        "num_seq_per_target": 2,
        "seed": 1,
        "device": "cpu",
        "python_executable": sys.executable,
    }
    base.update(overrides)
    return base


def test_mask_payload_is_the_complement() -> None:
    chains = {"A": [1, 2, 3, 4], "B": [10, 11]}
    payload = mask_payload({"A": [2, 4]}, chains, "complex")
    assert payload == {"complex": {"A": [1, 3], "B": [1, 2]}}


def test_step_writes_masked_designs(tmp_path: Path) -> None:
    params = _params(tmp_path)
    ctx = Ctx(params)
    step = ProteinmpnnMaskedDesignStep()
    step.run(ctx, [])
    out = ctx["designs"]
    assert out.data.shape == (2, 2)
    assert out.dims == ["design", "statistic"]
    assert list(out.labels["statistic"]) == ["score", "global_score"]
    assert list(out.labels["design"]) == ["design1", "design2"]
    assert out.info["n_fixed_residues"] == 4
    assert out.info["fixed_positions"] == {"A": [1, 3], "B": [1, 2]}
    assert out.info["sequences"] == ["ACDEFG", "ACDEFG"]
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert captured["fixed"] == {"complex": {"A": [1, 3], "B": [1, 2]}}
    assert captured["weights"].replace("\\", "/").endswith(
        "ProteinMPNN/vanilla_model_weights"
    )
    assert step.export(ctx)["n_fixed_residues"] == 4


def test_chain_filter_is_forwarded(tmp_path: Path) -> None:
    params = _params(tmp_path, chains="A")
    ctx = Ctx(params)
    ProteinmpnnMaskedDesignStep().run(ctx, [])
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert captured["chains"] == "A"


def test_parameter_errors(tmp_path: Path) -> None:
    cases = [
        ({"structure_path": str(tmp_path / "missing.pdb")}, "does not exist"),
        ({"structure_path": str(_complex(tmp_path / "complex.pdb")), "mask": ""}, "mask is required"),
        ({"mask": "Z:1"}, "is not present"),
        ({"mask": "A:9"}, "has no residue 9"),
        ({"mask": "A:1-3,B:1-2"}, "fixes every residue"),
        ({"chains": "C"}, "are not in the structure"),
        ({"model_name": "bogus"}, "model_name must be one of"),
        ({"device": "gpu"}, "device must be 'cpu' or 'cuda'"),
    ]
    for overrides, message in cases:
        ctx = Ctx(_params(tmp_path, **overrides))
        with pytest.raises(StepError, match=message):
            ProteinmpnnMaskedDesignStep().run(ctx, [])


def test_missing_runner_reports_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    ctx = Ctx(_params(tmp_path, proteinmpnn_path=str(repo)))
    with pytest.raises(StepError, match="protein_mpnn_run.py"):
        ProteinmpnnMaskedDesignStep().run(ctx, [])


def test_designer_failure_is_reported(tmp_path: Path) -> None:
    params = _params(tmp_path)
    repo = Path(params["proteinmpnn_path"])
    (repo / "protein_mpnn_run.py").write_text("import sys\nsys.stderr.write('boom')\nsys.exit(4)\n")
    ctx = Ctx(params)
    with pytest.raises(StepError, match="exit code 4"):
        ProteinmpnnMaskedDesignStep().run(ctx, [])


def test_output_shape_is_float32(tmp_path: Path) -> None:
    ctx = Ctx(_params(tmp_path))
    ProteinmpnnMaskedDesignStep().run(ctx, [])
    assert ctx["designs"].data.dtype == np.float32
