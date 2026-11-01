"""Hand checks for ESM masked-marginal scoring (no checkpoint required)."""
from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm_masked_marginal import (
    AA_ORDER,
    EsmMaskedMarginalStep,
    masked_marginal,
    parse_mutations,
)

AA_INDEX = {amino_acid: index for index, amino_acid in enumerate(
    "ACDEFGHIKLMNPQRSTVWYX"
)}
# ESM's vocabulary order differs from AA_ORDER; use arbitrary distinct ids.
VOCAB = {"<cls>": 0, "<pad>": 1, "<eos>": 2, "<unk>": 3}
for offset, amino_acid in enumerate(AA_ORDER, start=4):
    VOCAB[amino_acid] = offset
VOCAB["<mask>"] = 32
MASK_INDEX = 32


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _logits(position: int) -> np.ndarray:
    return np.array([((position * 7 + k) % 5) - 2.0 for k in range(20)])


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - values.max()
    exponential = np.exp(shifted)
    return exponential / exponential.sum()


def test_parse_mutations_hand():
    assert parse_mutations("A12V,G4D", 20) == [("A", 12, "V"), ("G", 4, "D")]
    assert parse_mutations("a12v", 20) == [("A", 12, "V")]
    assert parse_mutations(" A1C ; D2E ", 20) == [("A", 1, "C"), ("D", 2, "E")]
    with pytest.raises(StepError, match="not of the form"):
        parse_mutations("12V", 20)
    with pytest.raises(StepError, match="not of the form"):
        parse_mutations("AXV", 20)
    with pytest.raises(StepError, match="outside the sequence"):
        parse_mutations("A21V", 20)
    with pytest.raises(StepError, match="non-empty"):
        parse_mutations("", 20)


def test_masked_marginal_hand():
    sequence = "ACDE"
    rows = masked_marginal(sequence, "A1V,C2D", _logits)
    assert [row["mutation"] for row in rows] == ["A1V", "C2D"]

    for row, position in ((rows[0], 0), (rows[1], 1)):
        probabilities = _softmax(_logits(position))
        assert row["wt_prob"] == pytest.approx(
            probabilities[AA_ORDER.index(row["wild_type"])], rel=1e-12
        )
        assert row["mut_prob"] == pytest.approx(
            probabilities[AA_ORDER.index(row["mutant"])], rel=1e-12
        )
        assert row["log_ratio"] == pytest.approx(
            np.log(row["mut_prob"] / row["wt_prob"]), rel=1e-12
        )


def test_masked_marginal_rejects_bad_input():
    with pytest.raises(StepError, match="does not match wild-type"):
        masked_marginal("ACDE", "W1V", _logits)

    def short(_index):
        return np.zeros(3)

    with pytest.raises(StepError, match="20 logits"):
        masked_marginal("ACDE", "A1V", short)


class _FakeAlphabet:
    mask_idx = MASK_INDEX

    def get_idx(self, amino_acid):
        return VOCAB[amino_acid]

    def get_batch_converter(self):
        def convert(pairs):
            name, sequence = pairs[0]
            import torch

            tokens = torch.zeros((1, len(sequence) + 2), dtype=torch.long)
            tokens[0, 0] = VOCAB["<cls>"]
            tokens[0, -1] = VOCAB["<eos>"]
            for offset, character in enumerate(sequence, start=1):
                tokens[0, offset] = VOCAB[character]
            return [name], [sequence], tokens

        return convert


class _FakeModel:
    def eval(self):
        return self

    def to(self, device):
        return self

    def __call__(self, tokens):
        import torch

        length = tokens.shape[1]
        logits = torch.zeros((1, length, 33), dtype=torch.float32)
        for position in range(1, length - 1):
            values = _logits(position - 1)
            for offset, amino_acid in enumerate(AA_ORDER):
                logits[0, position, VOCAB[amino_acid]] = float(values[offset])
        return {"logits": logits}


def _protein_form(sequence: str):
    return encode_sequences([sequence], "sequence", "position", "protein")


def test_run_wiring_with_stub_model(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    fake_esm = types.SimpleNamespace(
        pretrained=types.SimpleNamespace(
            load_model_and_alphabet_local=lambda path: (_FakeModel(), _FakeAlphabet())
        )
    )
    monkeypatch.setitem(sys.modules, "esm", fake_esm)
    form = _protein_form("ACDE")
    ctx = Ctx({
        "mutations": "A1V,C2D",
        "model_path": str(tmp_path / "fake.pt"),
        "device": "cpu",
    })
    step = EsmMaskedMarginalStep()
    step.run(ctx, [form])

    output = ctx["out"]
    assert list(output.dims) == ["mutation", "statistic"]
    assert output.labels["mutation"] == {"A1V": 0, "C2D": 1}
    assert output.labels["statistic"] == {
        "wt_prob": 0,
        "mut_prob": 1,
        "log_ratio": 2,
    }
    expected = masked_marginal("ACDE", "A1V,C2D", _logits)
    np.testing.assert_allclose(
        output.data[:, 0],
        [row["wt_prob"] for row in expected],
        rtol=1e-6,
        atol=1e-8,
    )
    np.testing.assert_allclose(
        output.data[:, 1],
        [row["mut_prob"] for row in expected],
        rtol=1e-6,
        atol=1e-8,
    )
    np.testing.assert_allclose(
        output.data[:, 2],
        [row["log_ratio"] for row in expected],
        rtol=1e-5,
        atol=1e-6,
    )
    assert output.info["sequence"] == "ACDE"
    assert output.info["masked_positions"] == [1, 2]
    export = step.export(ctx)
    assert export["n_mutations"] == 2
    assert export["mutations"] == ["A1V", "C2D"]
    assert export["device"] == "cpu"


def test_run_errors(tmp_path):
    form = _protein_form("ACDE")
    with pytest.raises(StepError, match="model_path is required"):
        EsmMaskedMarginalStep().run(Ctx({}), [form])

    with pytest.raises(StepError, match="dims"):
        EsmMaskedMarginalStep().run(
            Ctx({"model_path": "x", "sequence_dim": "seq"}), [form]
        )

    with pytest.raises(StepError, match="out of range"):
        EsmMaskedMarginalStep().run(
            Ctx({"model_path": "x", "sequence_index": 3}), [form]
        )

    with pytest.raises(StepError, match="does not match wild-type"):
        EsmMaskedMarginalStep().run(
            Ctx({"model_path": "x", "mutations": "W1V"}), [form]
        )

    with pytest.raises(StepError, match="device must be"):
        EsmMaskedMarginalStep().run(
            Ctx({"model_path": "x", "device": "tpu"}), [form]
        )
