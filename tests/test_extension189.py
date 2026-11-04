"""Tests for rdkit_fragment_overlap and proteinmpnn_design_diversity."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.proteinmpnn_design_diversity import (
    ProteinmpnnDesignDiversityStep,
    cluster_ids,
    diversity_rows,
    pairwise_identities,
)
from src.task.step.steps.rdkit_fragment_overlap import (
    RdkitFragmentOverlapStep,
    brics_fragments,
    overlap_matrix,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _run(step, params, forms=()):
    output = params.get("output", "out")
    ctx = Ctx({"output": output, **params})
    step.run(ctx, list(forms))
    return ctx[output], step.export(ctx)


# ---------------------------------------------------------------- fragments


def test_overlap_matrix_hand_values() -> None:
    first = [{"a", "b"}, {"a"}]
    second = [{"a"}, {"b", "c"}]
    matrix = overlap_matrix(first, second)
    assert matrix.shape == (2, 2)
    assert matrix[0, 0] == pytest.approx(0.5)
    assert matrix[0, 1] == pytest.approx(1 / 3)
    assert matrix[1, 0] == pytest.approx(1.0)
    assert matrix[1, 1] == pytest.approx(0.0)


def test_brics_fragments_oracle() -> None:
    from rdkit import Chem
    from rdkit.Chem import BRICS

    molecule = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    expected = set()
    for fragment in BRICS.BRICSDecompose(molecule, minFragmentSize=4):
        cleaned = fragment.replace("[*]", "").replace("[1*]", "").replace("[2*]", "")
        if cleaned:
            expected.add(cleaned)
    if not expected:
        expected.add(Chem.MolToSmiles(molecule))
    assert brics_fragments(molecule, 4) == expected


def test_overlap_step_output() -> None:
    out, export = _run(
        RdkitFragmentOverlapStep(),
        {
            "smiles_a": "c1ccccc1 benzene\nCC(=O)Oc1ccccc1C(=O)O aspirin",
            "smiles_b": "c1ccccc1 benzene\nCCO ethanol",
            "min_fragment_size": 4,
        },
    )
    assert list(out.dims) == ["molecule_a", "molecule_b"]
    assert out.data.shape == (2, 2)
    assert out.data[0, 0] == pytest.approx(1.0)
    assert out.info["metric"] == "brics_jaccard"
    assert export["n_molecules_a"] == 2
    assert export["max_overlap"] == pytest.approx(1.0)


def test_overlap_errors() -> None:
    with pytest.raises(StepError, match="smiles_a is required"):
        _run(RdkitFragmentOverlapStep(), {"smiles_b": "CCO"})
    with pytest.raises(StepError, match="smiles_b is required"):
        _run(RdkitFragmentOverlapStep(), {"smiles_a": "CCO"})
    with pytest.raises(StepError, match="min_fragment_size"):
        _run(RdkitFragmentOverlapStep(), {"smiles_a": "CCO", "smiles_b": "CCN", "min_fragment_size": 0})
    with pytest.raises(StepError, match="must differ"):
        _run(
            RdkitFragmentOverlapStep(),
            {"smiles_a": "CCO", "smiles_b": "CCN", "molecule_a_dim": "m", "molecule_b_dim": "m"},
        )
    with pytest.raises(StepError, match="cannot parse"):
        _run(RdkitFragmentOverlapStep(), {"smiles_a": "notasmiles", "smiles_b": "CCO"})


# -------------------------------------------------------------- diversity


def test_pairwise_identities_hand() -> None:
    matrix = pairwise_identities(["AAAA", "AAAG", "AAAA"])
    assert matrix[0, 1] == pytest.approx(0.75)
    assert matrix[0, 2] == pytest.approx(1.0)
    assert matrix[1, 2] == pytest.approx(0.75)
    assert np.allclose(np.diag(matrix), 1.0)


def test_cluster_ids_and_rows() -> None:
    matrix = pairwise_identities(["AAAA", "AAAG", "AAAA"])
    assert cluster_ids(matrix, 0.9) == [0, 1, 0]
    rows = diversity_rows(["AAAA", "AAAG", "AAAA"], matrix, 0.9)
    assert rows[0]["mean_identity"] == pytest.approx(0.875)
    assert rows[0]["cluster"] == 0
    assert rows[1]["cluster"] == 1


def test_design_errors() -> None:
    with pytest.raises(StepError, match="at least two designs"):
        pairwise_identities(["AAAA"])
    with pytest.raises(StepError, match="native length"):
        pairwise_identities(["AAAA", "AAA"])
    with pytest.raises(StepError, match="standard amino acids"):
        pairwise_identities(["AAAA", "AAAX"])


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
]
lines = []
for index, record in enumerate(records):
    sequence = "ACDEFG" if index != 2 else "ACDEFY"
    lines.append(record)
    lines.append(sequence)
(seqs / (pdb.stem + ".fa")).write_text("\\n".join(lines) + "\\n")
(out / "captured.json").write_text(json.dumps({"argv": args}))
'''

FIXTURE = [
    "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
    "ATOM      2  CA  ALA A   2       3.800   0.000   0.000  1.00  0.00           C",
    "ATOM      3  CA  ALA A   3       7.600   0.000   0.000  1.00  0.00           C",
    "ATOM      4  CA  ALA A   4       1.000   0.000   0.000  1.00  0.00           C",
    "END",
]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ProteinMPNN"
    repo.mkdir()
    (repo / "protein_mpnn_run.py").write_text(FAKE_RUNNER)
    weights = repo / "vanilla_model_weights"
    weights.mkdir()
    (weights / "v_48_020.pt").write_bytes(b"x")
    return repo


def test_diversity_step(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = tmp_path / "mini.pdb"
    structure.write_text("\n".join(FIXTURE) + "\n")
    out, export = _run(
        ProteinmpnnDesignDiversityStep(),
        {
            "structure_path": str(structure),
            "proteinmpnn_path": str(repo),
            "weights_path": str(repo / "vanilla_model_weights"),
            "python_executable": sys.executable,
            "num_seq_per_target": 2,
            "identity_threshold": 0.9,
        },
    )
    assert list(out.dims) == ["design", "statistic"]
    assert out.data.shape == (2, 4)
    assert out.info["n_designs"] == 2
    assert out.info["sequences"] == ["ACDEFG", "ACDEFY"]
    assert out.data[0, 0] == pytest.approx(5 / 6)
    assert export["mean_pairwise_identity"] == pytest.approx(5 / 6, abs=1e-6)


def test_diversity_parameters(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = tmp_path / "mini.pdb"
    structure.write_text("\n".join(FIXTURE) + "\n")
    base = {"structure_path": str(structure), "proteinmpnn_path": str(repo), "python_executable": sys.executable}
    with pytest.raises(StepError, match="structure_path is required"):
        _run(ProteinmpnnDesignDiversityStep(), {})
    with pytest.raises(StepError, match="is not a file"):
        _run(ProteinmpnnDesignDiversityStep(), {**base, "structure_path": str(tmp_path / "nope.pdb")})
    with pytest.raises(StepError, match="identity_threshold"):
        _run(ProteinmpnnDesignDiversityStep(), {**base, "identity_threshold": 0.0})
    with pytest.raises(StepError, match="num_seq_per_target"):
        _run(ProteinmpnnDesignDiversityStep(), {**base, "num_seq_per_target": 1})
    with pytest.raises(StepError, match="weights_path"):
        _run(
            ProteinmpnnDesignDiversityStep(),
            {**base, "weights_path": str(tmp_path / "missing_weights")},
        )
