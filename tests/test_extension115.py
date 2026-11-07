"""ESM embedding operator (v1.20.0)."""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm_embedding import EsmEmbeddingStep

REAL_CHECKPOINT = os.environ.get("OPERON_ESM_CHECKPOINT", "")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


class _FakeAlphabet:
    cls_idx = 0
    eos_idx = 1
    padding_idx = 2

    def get_batch_converter(self):
        def convert(batch):
            labels = [label for label, _ in batch]
            strings = [sequence for _, sequence in batch]
            tokens = [
                [self.cls_idx]
                + [4 + (ord(residue) % 5) for residue in sequence]
                + [self.eos_idx]
                for sequence in strings
            ]
            return labels, strings, _tensor(tokens)

        return convert


def _tensor(rows):
    import torch

    width = max(len(row) for row in rows)
    padded = [row + [2] * (width - len(row)) for row in rows]
    return torch.tensor(padded, dtype=torch.int64)


class _FakeModel:
    """Deterministic stand-in that turns token ids into four visible numbers."""

    num_layers = 2

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        return self

    def __call__(self, tokens, repr_layers=None):
        import torch

        token_row = tokens[0].tolist()
        hidden = torch.tensor(
            [
                [
                    [
                        float(token) / 10.0,
                        float(token % 3),
                        float(position),
                        1.0,
                    ]
                    for position, token in enumerate(token_row)
                ]
            ],
            dtype=torch.float32,
        )
        requested = list(repr_layers or [self.num_layers])
        return {"representations": {layer: hidden for layer in requested}}


def _install_fake_esm(monkeypatch):
    module = types.SimpleNamespace(
        pretrained=types.SimpleNamespace(
            load_model_and_alphabet_local=lambda path: (
                _FakeModel(),
                _FakeAlphabet(),
            )
        )
    )
    monkeypatch.setitem(sys.modules, "esm", module)


def _sequence_form(sequences):
    return encode_sequences(sequences, "sequence", "position", "protein")


def _expected_embedding(sequence):
    tokens = [4 + (ord(residue) % 5) for residue in sequence]
    rows = [
        [token / 10.0, float(token % 3), float(position), 1.0]
        for position, token in enumerate(tokens, start=1)
    ]
    return np.mean(np.array(rows), axis=0)


def test_embeddings_match_deterministic_model(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    checkpoint = tmp_path / "fake.pt"
    checkpoint.write_bytes(b"checkpoint")
    _install_fake_esm(monkeypatch)

    step = EsmEmbeddingStep()
    form = _sequence_form(["ACD", "GG"])
    ctx = Ctx({"model_path": str(checkpoint)})
    step.run(ctx, [form])
    out = ctx["out"]

    assert out.dims == ["sequence", "embedding"]
    assert out.data.shape == (2, 4)
    assert out.data.dtype == np.float32
    assert list(out.labels["sequence"]) == list(form.labels["sequence"])
    assert list(out.labels["embedding"]) == ["0", "1", "2", "3"]
    np.testing.assert_allclose(
        out.data[0], _expected_embedding("ACD"), rtol=1e-6, atol=1e-6
    )
    np.testing.assert_allclose(
        out.data[1], _expected_embedding("GG"), rtol=1e-6, atol=1e-6
    )
    assert out.data[0].tolist() != out.data[1].tolist()
    assert out.info["pooling"] == "mean"
    assert out.info["embedding_dim"] == 4
    assert out.info["n_sequences"] == 2
    assert step.export(ctx)["n_sequences"] == 2


def test_embedding_is_deterministic(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    checkpoint = tmp_path / "fake.pt"
    checkpoint.write_bytes(b"checkpoint")
    _install_fake_esm(monkeypatch)
    form = _sequence_form(["ACD", "GG"])
    first = Ctx({"model_path": str(checkpoint)})
    second = Ctx({"model_path": str(checkpoint)})
    EsmEmbeddingStep().run(first, [form])
    EsmEmbeddingStep().run(second, [form])
    np.testing.assert_array_equal(first["out"].data, second["out"].data)


def test_embedding_errors(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    checkpoint = tmp_path / "fake.pt"
    checkpoint.write_bytes(b"checkpoint")
    _install_fake_esm(monkeypatch)
    step = EsmEmbeddingStep()
    form = _sequence_form(["ACD"])
    wrong_dims = Form(
        data=np.zeros((2, 2), dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {"a": 0, "b": 1}, "feature": {"f": 0, "g": 1}},
        info=dict(form.info),
    )
    empty_sequence = Form(
        data=np.full((1, 3), np.nan, dtype=np.float32),
        dims=["sequence", "position"],
        labels={"sequence": {"s1": 0}, "position": {"0": 0, "1": 1, "2": 2}},
        info=dict(form.info),
    )

    with pytest.raises(StepError, match="model_path is required"):
        step.run(Ctx({"model_path": ""}), [form])
    with pytest.raises(StepError, match="is not a file"):
        step.run(Ctx({"model_path": str(tmp_path / "missing.pt")}), [form])
    with pytest.raises(StepError, match="device must be 'cpu' or 'cuda'"):
        step.run(Ctx({"model_path": str(checkpoint), "device": "tpu"}), [form])
    with pytest.raises(StepError, match=r"expected a \[sequence, position\]"):
        step.run(Ctx({"model_path": str(checkpoint)}), [wrong_dims])
    with pytest.raises(StepError, match="sequence 0 is empty"):
        step.run(Ctx({"model_path": str(checkpoint)}), [empty_sequence])


@pytest.mark.skipif(
    not REAL_CHECKPOINT or not Path(REAL_CHECKPOINT).is_file(),
    reason="set OPERON_ESM_CHECKPOINT to a local esm2_t6_8M_UR50D.pt",
)
def test_embeddings_with_real_esm_checkpoint(tmp_path, monkeypatch):
    import sys as _sys

    if "esm" in _sys.modules and getattr(_sys.modules["esm"], "__file__", None) is None:
        monkeypatch.delitem(_sys.modules, "esm", raising=False)
    pytest.importorskip("torch")
    pytest.importorskip("esm")
    step = EsmEmbeddingStep()
    form = _sequence_form(["MKTAYIAKQR", "GGGG"])
    ctx = Ctx({"model_path": REAL_CHECKPOINT, "device": "cpu"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (2, 320)
    assert np.all(np.isfinite(out.data))
    assert not np.allclose(out.data[0], out.data[1], atol=1e-3)
    # Distinct segments of the same protein differ in embedding space.
    other = Ctx({"model_path": REAL_CHECKPOINT, "device": "cpu"})
    step.run(other, [_sequence_form(["MKTAYIAKQR"])])
    np.testing.assert_allclose(
        other["out"].data[0], out.data[0], rtol=1e-5, atol=1e-5
    )
