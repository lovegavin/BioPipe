"""ESM masked pseudo-likelihood operator (v1.21.0)."""
from __future__ import annotations

import math
import sys
import types

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._esm_common import AA_ORDER
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm_pseudo_likelihood import (
    EsmPseudoLikelihoodStep,
    masked_log_probs,
)

torch = pytest.importorskip("torch")

BOS, EOS, MASK = 0, 26, 25


class FakeAlphabet:
    """Minimal ESM alphabet: BOS=0, amino acids 1-20, mask=25, EOS=26."""

    mask_idx = MASK

    def get_idx(self, amino_acid):
        return AA_ORDER.index(amino_acid) + 1

    def get_batch_converter(self):
        def convert(batch):
            names = [name for name, _ in batch]
            sequences = [sequence for _, sequence in batch]
            rows = [
                [BOS] + [self.get_idx(aa) for aa in sequence] + [EOS]
                for sequence in sequences
            ]
            return names, sequences, torch.tensor(rows, dtype=torch.long)

        return convert


class ConstantModel:
    """All logits are zero, so every amino acid gets probability 1/20."""

    def to(self, device):
        return self

    def eval(self):
        return self

    def __call__(self, tokens):
        batch, length = tokens.shape
        return {"logits": torch.zeros(batch, length, 27)}


class ContextModel:
    """Logits depend on the (masked) context so batching must be exact."""

    def to(self, device):
        return self

    def eval(self):
        return self

    def __call__(self, tokens):
        batch, length = tokens.shape
        context = tokens.float().sum(dim=1).view(batch, 1, 1)
        offsets = torch.arange(20).float().view(1, 1, 20)
        positions = torch.arange(length).float().view(1, length, 1)
        logits = torch.zeros(batch, length, 27)
        logits[:, :, 1:21] = torch.sin(context * 0.11 + positions * 0.37 + offsets)
        return {"logits": logits}


def test_constant_model_gives_uniform_log_probability():
    sequence = "ACDE"
    scores = masked_log_probs(
        ConstantModel(), FakeAlphabet(), torch, sequence, "cpu"
    )
    # The model's 27-token vocabulary is uniform, and the operator reports the
    # un-renormalized log probability (the language-modelling partition).
    np.testing.assert_allclose(
        scores, np.full(4, -math.log(27.0)), rtol=1e-6, atol=0
    )


def test_batched_scores_match_per_position_reference():
    sequence = "MKWVTFISLL"
    alphabet = FakeAlphabet()
    model = ContextModel()
    batched = masked_log_probs(model, alphabet, torch, sequence, "cpu", batch_size=3)

    converter = alphabet.get_batch_converter()
    reference = np.empty(len(sequence))
    for position in range(len(sequence)):
        _, _, tokens = converter([("s", sequence)])
        tokens[0, position + 1] = MASK
        logits = model(tokens)["logits"][0, position + 1]
        log_probs = torch.log_softmax(logits, dim=-1)
        reference[position] = float(log_probs[alphabet.get_idx(sequence[position])])
    np.testing.assert_allclose(batched, reference, rtol=1e-6, atol=1e-7)


def test_non_standard_residue_is_rejected():
    with pytest.raises(StepError, match="not standard amino acids"):
        masked_log_probs(ConstantModel(), FakeAlphabet(), torch, "ACX", "cpu")


def _protein_form(sequences):
    return encode_sequences(
        sequences,
        "sequence",
        "position",
        "protein",
        labels={
            "sequence": {
                "s%d" % (index + 1): index for index in range(len(sequences))
            },
            "position": {
                str(index): index
                for index in range(max((len(s) for s in sequences), default=1))
            },
        },
        info_extra={"missing_code": np.nan},
    )


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


@pytest.fixture()
def fake_esm(monkeypatch):
    module = types.ModuleType("esm")
    pretrained = types.SimpleNamespace()
    calls = {}

    def load_model_and_alphabet_local(path):
        calls["path"] = path
        return ContextModel(), FakeAlphabet()

    pretrained.load_model_and_alphabet_local = load_model_and_alphabet_local
    module.pretrained = pretrained
    monkeypatch.setitem(sys.modules, "esm", module)
    return calls


def test_step_run_writes_position_statistic(tmp_path, fake_esm):
    checkpoint = tmp_path / "esm.pt"
    checkpoint.write_bytes(b"stub")
    step = EsmPseudoLikelihoodStep()
    ctx = Ctx({"model_path": str(checkpoint)})
    step.run(ctx, [_protein_form(["ACDE"])])
    out = ctx["out"]

    assert out.dims == ["position", "statistic"]
    assert list(out.labels["position"]) == ["1", "2", "3", "4"]
    reference = masked_log_probs(
        ContextModel(), FakeAlphabet(), torch, "ACDE", "cpu"
    )
    np.testing.assert_allclose(out.data[:, 0], reference, rtol=1e-6, atol=1e-7)
    assert out.info["n_positions"] == 4
    assert out.info["mean_log_prob"] == pytest.approx(float(reference.mean()))
    assert out.info["total_log_prob"] == pytest.approx(float(reference.sum()))
    assert step.export(ctx)["sequence"] == "ACDE"
    assert fake_esm["path"].endswith("esm.pt")


def test_step_errors(tmp_path):
    step = EsmPseudoLikelihoodStep()
    with pytest.raises(StepError, match="model_path is required"):
        step.run(Ctx({}), [_protein_form(["AC"])])
    missing = tmp_path / "nope.pt"
    with pytest.raises(StepError, match="is not a file"):
        step.run(Ctx({"model_path": str(missing)}), [_protein_form(["AC"])])
    checkpoint = tmp_path / "esm.pt"
    checkpoint.write_bytes(b"stub")
    with pytest.raises(StepError, match="exactly one sequence"):
        step.run(Ctx({"model_path": str(checkpoint)}), [_protein_form(["AC", "DE"])])
    with pytest.raises(StepError, match="batch_size"):
        step.run(
            Ctx({"model_path": str(checkpoint), "batch_size": 0}),
            [_protein_form(["AC"])],
        )
    with pytest.raises(StepError, match="dims"):
        step.run(
            Ctx({"model_path": str(checkpoint), "sequence_dim": "peptide"}),
            [_protein_form(["AC"])],
        )
