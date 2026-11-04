"""Tests for the masked interface ProteinMPNN designer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.proteinmpnn_masked_interface_design import (
    ProteinmpnnMaskedInterfaceDesignStep,
    interface_residues,
    mask_from_labels,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")

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
(pdb.parent / "captured.json").write_text(json.dumps({"fixed": fixed, "chains": value("--pdb_path_chains")}))
'''

ROWS = [
    (0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C"),
    (4.0, 0.0, 0.0, 2, "GLY", "A", "CA", "C"),
    (8.0, 0.0, 0.0, 3, "SER", "A", "CA", "C"),
    (0.0, 0.0, 2.0, 1, "THR", "B", "CA", "C"),
    (0.0, 0.0, 20.0, 2, "VAL", "B", "CA", "C"),
]


def _pdb_form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [
            numerics[0],
            numerics[1],
            numerics[2],
            numerics[3],
            encoded["resname"],
            encoded["chain"],
            encoded["atom_name"],
            encoded["element"],
        ]
    ).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _atom(serial, name, resname, chain, number, x, y, z, element="C"):
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2}"
    )


def _complex(path: Path) -> Path:
    lines = [
        _atom(index + 1, "CA", row[4], row[5], row[3], row[0], row[1], row[2])
        for index, row in enumerate(ROWS)
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


def _params(root: Path, **overrides):
    params = {
        "structure_path": str(_complex(root / "mini.pdb")),
        "binder_chains": "A",
        "target_chains": "B",
        "cutoff": 4.5,
        "proteinmpnn_path": str(_repo(root)),
        "python_executable": sys.executable,
        "num_seq_per_target": 2,
        "output": "designs",
    }
    params.update(overrides)
    return params


def test_interface_residues_hand_counted() -> None:
    labels = np.array([f"{row[5]}:{row[4]}:{row[3]}" for row in ROWS], dtype=object)
    chains = np.array([row[5] for row in ROWS], dtype=object)
    coords = np.asarray([row[:3] for row in ROWS], dtype=np.float64)
    binder, target, pairs = interface_residues(coords, labels, chains, ["A"], ["B"], 4.5)
    assert binder == {"A:ALA:1", "A:GLY:2"} and target == {"B:THR:1"}
    assert pairs == 2
    empty = interface_residues(coords, labels, chains, ["A"], ["B"], 1.0)
    assert empty == (set(), set(), 0)


def test_mask_from_labels() -> None:
    assert mask_from_labels(["A:ALA:1", "A:GLY:2", "B:THR:1"]) == {"A": [1, 2], "B": [1]}


def test_binder_mask_runner(tmp_path) -> None:
    ctx = Context(str(tmp_path / "design"), {"params": {}})
    ctx["complex"] = _pdb_form(ROWS)
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_masked_interface_design",
                "inputs": ["complex"],
                "params": _params(tmp_path),
            }
        ],
    )
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert captured["fixed"] == {"mini": {"A": [3], "B": [1, 2]}}
    assert captured["chains"] == "A"
    form = ctx["designs"]
    assert form.dims == ["design", "statistic"]
    assert form.data.shape == (2, 2)
    assert form.info["mask_side"] == "binder"
    assert form.info["interface_residues"] == {"A": [1, 2]}
    assert form.info["n_interface_residues"] == 2
    assert form.info["fixed_positions"] == {"A": [3], "B": [1, 2]}


def test_non_protein_interface_rows_are_ignored(tmp_path) -> None:
    rows = ROWS + [(0.0, 0.0, 2.2, 5, "HOH", "A", "O", "O")]
    ctx = Context(str(tmp_path / "design-water"), {"params": {}})
    ctx["complex"] = _pdb_form(rows)
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_masked_interface_design",
                "inputs": ["complex"],
                "params": _params(tmp_path, structure_path=str(_complex(tmp_path / "mini4.pdb"))),
            }
        ],
    )
    form = ctx["designs"]
    assert form.info["interface_residues"] == {"A": [1, 2]}
    assert form.info["n_interface_residues"] == 2


def test_target_mask_runner(tmp_path) -> None:
    ctx = Context(str(tmp_path / "design"), {"params": {}})
    ctx["complex"] = _pdb_form(ROWS)
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_masked_interface_design",
                "inputs": ["complex"],
                "params": _params(
                    tmp_path, mask_side="target", chains="B", structure_path=str(_complex(tmp_path / "mini2.pdb"))
                ),
            }
        ],
    )
    captured = json.loads((tmp_path / "captured.json").read_text())
    assert captured["fixed"] == {"mini2": {"A": [1, 2, 3], "B": [2]}}
    assert captured["chains"] == "B"


def test_validation_errors(tmp_path) -> None:
    step = ProteinmpnnMaskedInterfaceDesignStep()
    assert step.definition["inputs_arity"] == 1
    ctx = Context(str(tmp_path / "bad"), {"params": {}})
    ctx["complex"] = _pdb_form(ROWS)
    with pytest.raises(StepError, match="not found in the PDB form"):
        run(
            ctx,
            [
                {
                    "name": "proteinmpnn_masked_interface_design",
                    "inputs": ["complex"],
                    "params": _params(tmp_path, binder_chains="Z"),
                }
            ],
        )
