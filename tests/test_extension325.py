"""esm3_embedding: per-residue ESM-3 embeddings."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm3_embedding import encode_batch


class _FakeOutput:
    def __init__(self, embeddings):
        self.embeddings = embeddings


class _FakeModel:
    def __init__(self, width=8):
        self.width = width

    def encode(self, protein):
        class _Tokens:
            def __init__(self, sequence):
                import torch

                self.sequence = torch.zeros(len(sequence) + 2, dtype=torch.long)

        sequence = protein.sequence if hasattr(protein, "sequence") else protein
        return _Tokens(sequence)

    def forward(self, *, sequence_tokens=None):
        import torch

        length = sequence_tokens.shape[1]
        values = torch.arange(length * self.width, dtype=torch.float32).reshape(1, length, self.width)
        return _FakeOutput(values)


def test_encode_batch_strips_special_tokens():
    model = _FakeModel(width=4)
    import torch

    values = encode_batch(model, ["ACDE", "ACDEFG"], "cpu")
    assert values[0].shape == (4, 4)
    assert values[1].shape == (6, 4)
    assert values[0][0][0] == pytest.approx(4.0)


def test_run_round_trip(monkeypatch, tmp_path):
    import src.task.step.steps.esm3_embedding as module

    monkeypatch.setattr(module, "load_model", lambda name, device: _FakeModel(width=5))
    monkeypatch.setitem(module._MODELS, "esm3-sm-open-v1", "esm3_sm_open_v1")
    form = encode_sequences(["ACDE"], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["protein"] = form
    run(ctx, [{"name": "esm3_embedding", "inputs": ["protein"], "params": {"output": "embeddings"}}])
    table = ctx["embeddings"]
    assert table.data.shape == (1, 4, 5)
    assert table.info["embedding_dim"] == 5


def test_validation_errors():
    with pytest.raises(StepError, match="device must be"):
        from src.task.step.steps.esm3_embedding import Esm3EmbeddingStep

        ctx = Context("/tmp/operon_esm3", {"params": {}})
        ctx.step_params = {"output": "embeddings", "device": "tpu"}
        Esm3EmbeddingStep().run(ctx, [encode_sequences(["ACDE"], "sequence", "position", "protein")])


def test_real_esm3(monkeypatch):
    import os

    if os.environ.get("OPERON_ESM3_REAL") != "1":
        pytest.skip("set OPERON_ESM3_REAL=1 to run the real ESM-3 check")
    pytest.importorskip("esm")
    from src.task.step.steps import esm3_embedding as module

    module._CACHE.clear()
    ctx = Context("/tmp/operon_esm3_real", {"params": {}})
    ctx["protein"] = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    run(ctx, [{"name": "esm3_embedding", "inputs": ["protein"], "params": {"output": "embeddings"}}])
    table = ctx["embeddings"]
    assert table.data.shape == (1, 14, 1536)
    assert np.isfinite(table.data).all()
