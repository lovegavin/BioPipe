"""Runner-level contract checks for the v1.31.0 operators."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from src.core.forms.form import Form  # noqa: E402
from src.task.context.base import Context  # noqa: E402
from src.task.runner import run  # noqa: E402

from test_extension164 import _repo, _structure  # noqa: E402
from test_extension167 import _atom as _cys_atom  # noqa: E402
from test_extension167 import _pdb_form as _disulfide_form  # noqa: E402


def _embedding_form(matrix: np.ndarray) -> Form:
    matrix = np.asarray(matrix, dtype=np.float32)
    rows, columns = matrix.shape
    return Form(
        data=matrix,
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"seq{index + 1}": index for index in range(rows)},
            "embedding": {f"e{index}": index for index in range(columns)},
        },
        info={"missing_code": np.nan},
    )


def test_embedding_chain(tmp_path: Path) -> None:
    matrix = np.array(
        [[1.0, 0.0, 1.0], [0.0, 1.0, 1.0], [1.0, 1.0, 0.0], [0.2, 0.2, 0.2]]
    )
    ctx = Context(tmp_path / "task", {"params": {}})
    ctx["embeddings"] = _embedding_form(matrix)
    run(
        ctx,
        [
            {
                "name": "esm_embedding_pca",
                "inputs": ["embeddings"],
                "params": {"n_components": 2, "output": "pca"},
            },
            {
                "name": "esm_embedding_neighbors",
                "inputs": ["embeddings"],
                "params": {"k": 2, "metric": "cosine", "output": "neighbors"},
            },
        ],
    )
    assert ctx["pca"].data.shape == (4, 2)
    assert ctx["neighbors"].data.shape == (4, 2)
    assert (tmp_path / "task" / "output" / "steps" / "02_esm_embedding_neighbors.json").is_file()


def test_structure_chain(tmp_path: Path) -> None:
    atoms = [
        _cys_atom("A", "CYS", 26, "SG", 0.0, 0.0, 0.0),
        _cys_atom("A", "ASP", 1, "OD1", 5.0, 0.0, 0.0, "O"),
        _cys_atom("B", "CYS", 84, "SG", 2.0, 0.0, 0.0),
        _cys_atom("B", "LYS", 5, "NZ", 7.5, 0.0, 0.0, "N"),
    ]
    ctx = Context(tmp_path / "task2", {"params": {}})
    ctx["structure"] = _disulfide_form(atoms)
    run(
        ctx,
        [
            {
                "name": "structure_disulfide_bonds",
                "inputs": ["structure"],
                "params": {"max_distance": 2.5, "output": "disulfides"},
            },
            {
                "name": "structure_salt_bridges",
                "inputs": ["structure"],
                "params": {"max_distance": 4.0, "output": "bridges"},
            },
        ],
    )
    assert ctx["disulfides"].data.shape == (1, 1)
    assert ctx["bridges"].data.shape == (1, 1)


def test_entropy_through_runner(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    structure = _structure(tmp_path)
    ctx = Context(tmp_path / "task3", {"params": {}})
    run(
        ctx,
        [
            {
                "name": "proteinmpnn_position_entropy",
                "inputs": [],
                "params": {
                    "structure_path": str(structure),
                    "proteinmpnn_path": str(repo),
                    "num_seq_per_target": 4,
                    "sampling_temp": "0.1",
                    "seed": 1,
                    "model_name": "v_48_020",
                    "device": "cpu",
                    "output": "entropy",
                },
            }
        ],
    )
    assert ctx["entropy"].data.shape == (6, 4)
    assert (
        tmp_path / "task3" / "output" / "steps" / "01_proteinmpnn_position_entropy.json"
    ).is_file()
