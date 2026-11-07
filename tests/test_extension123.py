"""Tests for esm_variant_effect."""
from __future__ import annotations

import sys
import types

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm_variant_effect import (
    STATISTICS,
    EsmVariantEffectStep,
    masked_position_log_probs,
    parse_positions,
)

torch = pytest.importorskip("torch")

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
BOS, EOS, MASK = 0, 26, 25


class FakeAlphabet:
    mask_idx = MASK

    def get_idx(self, amino_acid):
        if amino_acid == "-":
            return 24
        return 1 + AA_ORDER.index(amino_acid)

    def get_batch_converter(self):
        def convert(records):
            labels = [name for name, _sequence in records]
            sequences = [sequence for _name, sequence in records]
            width = max(len(sequence) for sequence in sequences) + 2
            tokens = torch.zeros((len(records), width), dtype=torch.long)
            for row, sequence in enumerate(sequences):
                tokens[row, 0] = BOS
                for index, amino_acid in enumerate(sequence):
                    tokens[row, index + 1] = self.get_idx(amino_acid)
                tokens[row, len(sequence) + 1] = EOS
            return labels, sequences, tokens

        return convert


class ContextModel:
    """Deterministic stand-in whose logits depend on the token context."""

    num_layers = 1

    def __call__(self, tokens, **kwargs):
        batch, length = tokens.shape
        logits = torch.zeros((batch, length, 27))
        for position in range(length):
            for row in range(batch):
                for token in range(27):
                    logits[row, position, token] = float(
                        np.sin(0.37 * position + 0.11 * token)
                    ) * 3.0
        return {"logits": logits, "representations": {1: torch.zeros((batch, length, 8))}}

    def to(self, device):
        return self

    def eval(self):
        return self


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


def test_parse_positions():
    assert parse_positions("1-3", 10) == [0, 1, 2]
    assert parse_positions("2, 4-5", 10) == [1, 3, 4]
    assert parse_positions("1", 1) == [0]
    assert parse_positions("", 10) == list(range(10))
    with pytest.raises(StepError, match="is not of the form 12-16"):
        parse_positions("1-abc", 10)
    with pytest.raises(StepError, match="is not an integer"):
        parse_positions("abc", 10)
    with pytest.raises(StepError, match="starts after it ends"):
        parse_positions("5-2", 10)
    with pytest.raises(StepError, match="outside the sequence of length 4"):
        parse_positions("9", 4)
    with pytest.raises(StepError, match="selected no residue"):
        parse_positions(",;", 10)


def test_masked_position_log_probs_matches_manual_softmax():
    sequence = "ACDE"
    positions = [0, 2]
    values = masked_position_log_probs(
        ContextModel(), FakeAlphabet(), torch, sequence, "cpu", positions
    )
    assert values.shape == (2, 20)
    _labels, _sequences, tokens = FakeAlphabet().get_batch_converter()(
        [("x", sequence)]
    )
    logits = ContextModel()(tokens.clone())["logits"][0]
    for row, position in enumerate(positions):
        log_probs = torch.log_softmax(logits[position + 1], dim=-1)
        expected = [float(log_probs[FakeAlphabet().get_idx(aa)]) for aa in AA_ORDER]
        np.testing.assert_allclose(values[row], expected, rtol=1e-6, atol=1e-7)
        assert float(np.exp(values[row]).sum()) <= 1.0 + 1e-6


def test_batch_matches_single_position():
    sequence = "ACDEFGHIKL"
    batched = masked_position_log_probs(
        ContextModel(), FakeAlphabet(), torch, sequence, "cpu", list(range(0, 10, 2)), batch_size=3
    )
    for row, position in enumerate(range(0, 10, 2)):
        single = masked_position_log_probs(
            ContextModel(), FakeAlphabet(), torch, sequence, "cpu", [position]
        )
        np.testing.assert_allclose(batched[row], single[0], rtol=1e-6, atol=1e-7)


def test_step_run_writes_mutation_statistic(tmp_path, fake_esm):
    checkpoint = tmp_path / "esm.pt"
    checkpoint.write_bytes(b"stub")
    step = EsmVariantEffectStep()
    ctx = Ctx({"model_path": str(checkpoint), "positions": "2"})
    step.run(ctx, [_protein_form(["ACDE"])])
    form = ctx["out"]
    assert form.dims == ["mutation", "statistic"]
    assert len(form.labels["mutation"]) == 19
    labels = list(form.labels["mutation"])
    assert labels[0] == "C2A"
    assert "C2C" not in labels
    assert labels[-1] == "C2Y"
    assert list(form.labels["statistic"]) == list(STATISTICS)
    assert form.info["positions"] == [2]
    assert form.info["sequence"] == "ACDE"
    assert len(form.info["top_mutations"]) == 10
    export = step.export(ctx)
    assert export["n_mutations"] == 19
    assert export["positions"] == 1


def test_step_llr_values_match_unmasked_model(tmp_path, fake_esm):
    checkpoint = tmp_path / "esm.pt"
    checkpoint.write_bytes(b"stub")
    step = EsmVariantEffectStep()
    ctx = Ctx({"model_path": str(checkpoint), "positions": "1-2"})
    step.run(ctx, [_protein_form(["WY"])])
    form = ctx["out"]
    assert form.data.shape == (38, len(STATISTICS))
    assert list(form.labels["mutation"])[:2] == ["W1A", "W1C"]
    llr_position = form.labels["statistic"]["llr"]
    wt_position = form.labels["statistic"]["wt_log_prob"]
    mut_position = form.labels["statistic"]["mut_log_prob"]
    np.testing.assert_allclose(
        form.data[:, llr_position],
        form.data[:, mut_position] - form.data[:, wt_position],
        rtol=1e-6,
        atol=1e-6,
    )
    assert np.all(np.isfinite(form.data))


def _unknown_form():
    form = _protein_form(["ACDE"])
    form.info["alphabet_map"] = {**form.info["alphabet_map"], "X": 22}
    form.data[0, 2] = 22.0
    return form


def test_step_errors(tmp_path, fake_esm):
    checkpoint = tmp_path / "esm.pt"
    checkpoint.write_bytes(b"stub")
    step = EsmVariantEffectStep()
    with pytest.raises(StepError, match="exactly one sequence"):
        step.run(Ctx({"model_path": str(checkpoint)}), [_protein_form(["ACD", "EFG"])])
    with pytest.raises(StepError, match="outside the sequence of length"):
        step.run(Ctx({"model_path": str(checkpoint), "positions": "9"}), [_protein_form(["ACDE"])])
    with pytest.raises(StepError, match="not standard amino acids"):
        step.run(Ctx({"model_path": str(checkpoint)}), [_unknown_form()])
    with pytest.raises(StepError, match="model_path is required"):
        step.run(Ctx({}), [_protein_form(["ACDE"])])
    with pytest.raises(StepError, match="batch_size"):
        step.run(
            Ctx({"model_path": str(checkpoint), "batch_size": 0}),
            [_protein_form(["ACDE"])],
        )


@pytest.mark.skipif(
    __import__("os").environ.get("OPERON_ESM_CHECKPOINT", "") == "",
    reason="OPERON_ESM_CHECKPOINT is not set",
)
def test_official_checkpoint_variant_effect():
    import os

    checkpoint = os.environ["OPERON_ESM_CHECKPOINT"]
    step = EsmVariantEffectStep()
    ctx = Ctx({"model_path": checkpoint, "positions": "2", "device": "cpu"})
    step.run(ctx, [_protein_form(["ACDE"])])
    form = ctx["out"]
    assert form.data.shape == (19, len(STATISTICS))
    assert np.all(np.isfinite(form.data))
    assert form.info["model_path"] == checkpoint
