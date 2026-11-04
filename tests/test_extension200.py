"""Runner-level contract tests for the v1.38.0 operators."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


def _ctx(tmp_path: Path) -> Context:
    return Context(tmp_path / "task", {"params": {}})


def _embedding_form() -> Form:
    data = np.asarray([[1.0, 0.0], [2.0, 1.0], [3.0, 0.0], [4.0, 2.0]], dtype=np.float32)
    return Form(
        data=data,
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"s{index}": index for index in range(4)},
            "embedding": {"e0": 0, "e1": 1},
        },
        info={"missing_code": np.nan},
        axis_info={},
    )


def _pdb_form():
    from src.reader import pick_reader, read_source

    reader = pick_reader(str(FIXTURE)).implementation()
    return read_source(
        str(FIXTURE),
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
        reader_id=reader.definition["id"],
    )


def test_pca_loadings_through_runner(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ctx["embeddings"] = _embedding_form()
    run(ctx, [{
        "name": "esm_embedding_pca_loadings",
        "inputs": ["embeddings"],
        "params": {"output": "loadings", "n_components": 2},
    }])
    out = ctx["loadings"]
    assert out.data.shape == (2, 2)
    assert (tmp_path / "task" / "output" / "steps" / "01_esm_embedding_pca_loadings.json").is_file()


def test_kmer_and_restriction_through_runner(tmp_path: Path) -> None:
    from src.task.step.steps._sequence_common import encode_sequences

    ctx = _ctx(tmp_path)
    ctx["dna"] = encode_sequences(["GAATTCACGT", "AAAACCCC"], "sequence", "position", "dna")
    run(ctx, [
        {"name": "sequence_kmer_profile", "inputs": ["dna"],
         "params": {"output": "kmer", "k_mer": 2}},
        {"name": "sequence_restriction_sites", "inputs": ["dna"],
         "params": {"output": "sites"}},
    ])
    assert ctx["kmer"].data.shape == (2, 5)
    assert ctx["sites"].data.shape == (2, 3)
    assert ctx["sites"].data[0, 0] == pytest.approx(1.0)


def test_chi_angles_through_runner(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ctx["structure"] = _pdb_form()
    run(ctx, [{
        "name": "structure_chi_angles",
        "inputs": ["structure"],
        "params": {"output": "chi"},
    }])
    assert ctx["chi"].data.shape == (16, 3)


def test_reaction_through_runner(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    ctx = _ctx(tmp_path)
    run(ctx, [{
        "name": "rdkit_reaction_smarts_apply",
        "inputs": [],
        "params": {
            "output": "products",
            "smiles": "COc1ccccc1\n",
            "reaction_smarts": "[CH3:1][O:2][c:3]>>[O:2][c:3]",
        },
    }])
    assert ctx["products"].data.shape == (1, 3)
