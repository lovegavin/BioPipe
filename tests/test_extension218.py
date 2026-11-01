"""Tests for proteinmpnn_design_cluster."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.proteinmpnn_design_cluster import (
    ProteinmpnnDesignClusterStep,
    cluster_rows,
    consensus_sequence,
)

FAKE_RUNNER = '''
import json, sys
from pathlib import Path

args = sys.argv[1:]
out = Path(args[args.index("--out_folder") + 1])
pdb = Path(args[args.index("--pdb_path") + 1])
seqs = out / "seqs"
seqs.mkdir(parents=True, exist_ok=True)
records = [
    ">" + pdb.stem + ", T=0.1, seed=1, num_res=6, num_ligand_res=0",
    ">T=0.1, sample=1, score=1.1, global_score=1.0, seq_recovery=0.5",
    ">T=0.1, sample=2, score=1.2, global_score=1.1, seq_recovery=0.4",
    ">T=0.1, sample=3, score=1.3, global_score=1.2, seq_recovery=0.3",
    ">T=0.1, sample=4, score=1.4, global_score=1.3, seq_recovery=0.2",
]
sequences = ["ACDEFG", "ACDEFG", "ACDEFG", "ACDEFY", "ACDEWY"]
lines = []
for record, sequence in zip(records, sequences):
    lines.append(record)
    lines.append(sequence)
(seqs / (pdb.stem + ".fa")).write_text("\\n".join(lines) + "\\n")
(out / "captured.json").write_text(json.dumps({"argv": args}))
'''

FIXTURE = [
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
    "ATOM      2  CA  ALA A   2       3.800   0.000   0.000  1.00  0.00           C",
    "ATOM      3  CA  ALA A   3       7.600   0.000   0.000  1.00  0.00           C",
    "END",
]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"x")
    return repo


def _structure(tmp_path: Path) -> Path:
    structure = tmp_path / "mini.pdb"
    structure.write_text("\n".join(FIXTURE) + "\n")
    return structure


def test_cluster_rows_hand_values() -> None:
    identities = np.array(
        [
            [1.0, 1.0, 5 / 6, 0.5],
            [1.0, 1.0, 5 / 6, 0.5],
            [5 / 6, 5 / 6, 1.0, 2 / 3],
            [0.5, 0.5, 2 / 3, 1.0],
        ]
    )
    clusters = [0, 0, 0, 1]
    rows = cluster_rows(identities, clusters)
    assert [row[0] for row in rows] == [1.0, 1.0, 1.0, 2.0]
    assert [row[1] for row in rows] == [3.0, 3.0, 3.0, 1.0]
    assert rows[0][2] == pytest.approx((1.0 + 5 / 6) / 2)
    assert rows[3][2] == pytest.approx(1.0)


def test_consensus_sequence() -> None:
    sequences = ["ACDEFG", "ACDEFG", "ACDEFY"]
    assert consensus_sequence(sequences, [0, 1]) == "ACDEFG"
    assert consensus_sequence(sequences, [0, 1, 2]) == "ACDEFG"
    assert consensus_sequence(sequences, [2]) == "ACDEFY"


def test_step_clusters_designs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    step = ProteinmpnnDesignClusterStep()
    ctx = Ctx(
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo),
            "num_seq_per_target": 4,
            "python_executable": sys.executable,
            "identity_threshold": 0.9,
            "output": "clusters",
        }
    )
    step.run(ctx, [])
    out = ctx["clusters"]
    assert list(out.dims) == ["design", "statistic"]
    assert out.data.shape == (4, 4)
    # identity 0.9 splits the designs into {1,2}, {3} and {4}.
    assert out.info["n_designs"] == 4
    assert out.info["n_clusters"] >= 2
    assert sorted(out.info["cluster_sizes"]) == sorted(out.info["cluster_sizes"])
    first = out.data[0]
    assert first[0] == out.data[1][0]
    export = step.export(ctx)
    assert export["n_designs"] == 4
    assert export["identity_threshold"] == 0.9


def test_parameter_errors(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    base = {
        "structure_path": str(structure),
        "proteinmpnn_path": str(repo),
        "python_executable": sys.executable,
    }
    step = ProteinmpnnDesignClusterStep()
    with pytest.raises(StepError, match="structure_path is required"):
        step.run(Ctx({}), [])
    with pytest.raises(StepError, match="does not exist"):
        step.run(Ctx({"structure_path": str(tmp_path / "nope.pdb")}), [])
    with pytest.raises(StepError, match="identity_threshold"):
        step.run(Ctx({**base, "identity_threshold": 1.5}), [])
    with pytest.raises(StepError, match="model_name"):
        step.run(Ctx({**base, "model_name": "v_99"}), [])
    with pytest.raises(StepError, match="takes no graph inputs"):
        step.run(Ctx(base), [object()])
