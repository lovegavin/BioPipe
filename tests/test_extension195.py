from __future__ import annotations

import numpy as np

from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"


def test_gc_profile_through_runner(tmp_path) -> None:
    context = Context(tmp_path / "task", {"params": {}})
    context["dna"] = encode_sequences(["ACGTACGT", "GGCC"], "sequence", "position", "dna")
    run(
        context,
        [
            {
                "name": "sequence_gc_profile",
                "inputs": ["dna"],
                "params": {"output": "gc", "sequence_dim": "sequence", "position_dim": "position", "window": 4},
            }
        ],
    )
    out = context["gc"]
    assert list(out.dims) == ["sequence", "statistic"]
    assert (tmp_path / "task" / "output" / "steps" / "01_sequence_gc_profile.json").is_file()


def test_outlier_scan_through_runner(tmp_path) -> None:
    context = Context(tmp_path / "task", {"params": {}})
    context["embeddings"] = Form(
        data=np.asarray([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [9.0, 9.0]], dtype=np.float32),
        dims=["sample", "embedding"],
        labels={"sample": {"s1": 0, "s2": 1, "s3": 2, "s4": 3}, "embedding": {"e1": 0, "e2": 1}},
        info={"missing_code": np.nan},
        axis_info={},
    )
    run(
        context,
        [
            {
                "name": "esm_embedding_outlier_scan",
                "inputs": ["embeddings"],
                "params": {"output": "outliers", "sample_dim": "sample", "embedding_dim": "embedding"},
            }
        ],
    )
    assert context["outliers"].data.shape == (4, 3)
    assert context["outliers"].labels["sample"]["s4"] == 3


def test_scaffold_diversity_through_runner(tmp_path) -> None:
    context = Context(tmp_path / "task", {"params": {}})
    run(
        context,
        [
            {
                "name": "rdkit_scaffold_diversity",
                "inputs": [],
                "params": {"smiles": "c1ccccc1\nCCO\n", "output": "scaffolds"},
            }
        ],
    )
    assert context["scaffolds"].data.shape == (2, 3)
    assert context["scaffolds"].info["n_scaffolds"] == 2
