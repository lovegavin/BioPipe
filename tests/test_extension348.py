"""esm3_sequence_generation: prompt parsing, contract and gated real run."""

import os

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import esm3_sequence_generation as module
from src.task.step.steps.esm3_sequence_generation import (
    Esm3SequenceGenerationStep,
    encode_generated,
    generate_sequence,
    mask_positions,
    parse_prompt,
)


def test_parse_prompt_and_mask_positions():
    assert parse_prompt(" mkta_yia ") == "MKTA_YIA"
    assert mask_positions("MKTA_YIA") == [5]
    with pytest.raises(StepError, match="prompt is required"):
        parse_prompt("   ")
    with pytest.raises(StepError, match="unsupported characters"):
        parse_prompt("MKTA-YIA_")
    with pytest.raises(StepError, match="at least one masked position"):
        parse_prompt("MKTAYIAK")


def test_encode_generated_round_trip():
    form, info = encode_generated("MKTAX", "esm3_sequence_generation")
    assert form.dims == ["sequence", "position"]
    assert form.data.shape == (1, 5)
    assert info["sequence"] == "MKTAX"


def test_run_with_stubbed_model(monkeypatch):
    class Fake:
        def generate(self, protein, config):
            return type("R", (), {"sequence": protein.sequence.replace("_", "L")})()

    monkeypatch.setattr(module, "load_model", lambda name, device: Fake())
    ctx = Context("/tmp/operon_esm3_generation", {"params": {}})
    params = {"output": "generation", "prompt": "MKTAY___", "num_steps": 3, "temperature": 0.5, "seed": 7}
    ctx.step_params = params
    result = Esm3SequenceGenerationStep().run(ctx, [])
    assert result.dims == ["sequence", "position"]
    assert result.data.shape == (1, 8)
    assert result.info["generated_sequence"] == "MKTAYLLL"
    assert result.info["n_masked"] == 3
    assert result.info["n_changed"] == 3
    assert result.info["seed"] == 7


def test_validation_errors():
    ctx = Context("/tmp/operon_esm3_generation_err", {"params": {}})
    with pytest.raises(StepError, match="device must be"):
        ctx.step_params = {"prompt": "MK_", "device": "tpu"}
        Esm3SequenceGenerationStep().run(ctx, [])
    with pytest.raises(StepError, match="num_steps must be"):
        ctx.step_params = {"prompt": "MK_", "num_steps": 100}
        Esm3SequenceGenerationStep().run(ctx, [])


@pytest.mark.skipif(os.environ.get("OPERON_ESM3_REAL") != "1", reason="set OPERON_ESM3_REAL=1")
def test_real_generation_matches_direct_api():
    import torch
    from esm.models.esm3 import ESM3
    from esm.sdk.api import ESMProtein, GenerationConfig

    prompt = "MKTAYIAKQR________"
    model = ESM3.from_pretrained("esm3_sm_open_v1", device=torch.device("cpu")).float().eval()
    torch.manual_seed(11)
    direct = model.generate(ESMProtein(sequence=prompt), GenerationConfig(track="sequence", num_steps=8, temperature=0.7)).sequence
    produced = generate_sequence(model, prompt, num_steps=8, temperature=0.7, seed=11)
    assert produced == direct
    assert produced[:10] == prompt[:10]
    assert len(produced) == len(prompt)
