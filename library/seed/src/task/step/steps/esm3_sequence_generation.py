"""ESM-3 sequence generation with masked prompts."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import PROTEIN_CHARS, PROTEIN_MAP, encode_sequences

STANDARD = frozenset("ACDEFGHIKLMNPQRSTVWY")
MASK = "_"
_DEFAULT_MODEL = "esm3_sm_open_v1"


def parse_prompt(text: str) -> str:
    """Validate and normalise an ESM-3 prompt ('_' marks a position to sample)."""

    prompt = (text or "").strip().upper().replace(" ", "")
    if not prompt:
        raise StepError("esm3_sequence_generation: prompt is required")
    unsupported = sorted({char for char in prompt if char not in STANDARD and char != MASK})
    if unsupported:
        raise StepError(
            "esm3_sequence_generation: the prompt contains unsupported characters "
            + ", ".join(unsupported)
        )
    if MASK not in prompt:
        raise StepError(
            "esm3_sequence_generation: the prompt must contain at least one masked "
            "position ('_') to generate"
        )
    return prompt


def mask_positions(prompt: str) -> list[int]:
    """Return 1-based positions of masked residues."""

    return [index + 1 for index, char in enumerate(prompt) if char == MASK]


def load_model(name: str, device: str):
    """Load and cache an ESM-3 checkpoint on the requested device."""

    import torch
    from esm.models.esm3 import ESM3

    global _MODEL
    key = (name, device)
    if _MODEL is not None and _MODEL[0] == key:
        return _MODEL[1]
    torch_device = torch.device(device)
    model = ESM3.from_pretrained(name, device=torch_device)
    model = model.float().eval()
    _MODEL = (key, model)
    return model


_MODEL = None


def generate_sequence(
    model,
    prompt: str,
    *,
    num_steps: int = 8,
    temperature: float = 0.7,
    seed: int = 0,
) -> str:
    """Run the ESM-3 sequence track and return the generated sequence."""

    import torch
    from esm.sdk.api import ESMProtein, GenerationConfig

    torch.manual_seed(int(seed))
    protein = ESMProtein(sequence=prompt)
    config = GenerationConfig(track="sequence", num_steps=int(num_steps), temperature=float(temperature))
    result = model.generate(protein, config)
    sequence = str(getattr(result, "sequence", "") or "")
    if not sequence:
        raise StepError("esm3_sequence_generation: ESM-3 returned no sequence")
    return sequence


def encode_generated(sequence: str, operator: str) -> tuple[Form, dict]:
    """Wrap a generated protein sequence in the shared sequence Form contract."""

    letters = "".join(char if char in STANDARD else "X" for char in sequence)
    form = encode_sequences([letters], "sequence", "position", "protein")
    form.info.update({"generated_sequence": letters})
    return form, {"sequence": letters}


class Esm3SequenceGenerationStep(Step):
    """Sample a protein sequence from an ESM-3 masked prompt."""

    provider = "operon-core"
    parameters_file = "esm3_sequence_generation.Esm3SequenceGenerationStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_sequence_generation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 序列生成",
        "category": "Machine Learning",
        "icon": "Brain",
        "description": "Sample protein sequences from an ESM-3 masked prompt on CPU or CUDA.",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "dims": ["sequence", "position"],
                    "columns": [],
                    "labels": {},
                },
                "info": {
                    "representation": {"type": "string", "const": "sequence_codes"},
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "esm3"},
        "dependencies": ["torch", "esm"],
        "dependency_imports": ["torch", "esm"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        prompt = parse_prompt(str(params.get("prompt", "")))
        num_steps = int(params.get("num_steps", 8))
        temperature = float(params.get("temperature", 0.7))
        seed = int(params.get("seed", 0))
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_sequence_generation: device must be 'cpu' or 'cuda'")
        if not 1 <= num_steps <= 64:
            raise StepError("esm3_sequence_generation: num_steps must be between 1 and 64")
        if not 0.05 <= temperature <= 2.0:
            raise StepError("esm3_sequence_generation: temperature must be between 0.05 and 2.0")
        model = load_model(str(params.get("model", _DEFAULT_MODEL) or _DEFAULT_MODEL), device)
        try:
            sequence = generate_sequence(model, prompt, num_steps=num_steps, temperature=temperature, seed=seed)
        except ModuleNotFoundError as exc:  # pragma: no cover - dependency gate
            raise StepError(
                "esm3_sequence_generation: the ESM package is required; install it with pip from the evolutionaryscale/esm repository"
            ) from exc
        form, info = encode_generated(sequence, "esm3_sequence_generation")
        masks = mask_positions(prompt)
        changed = sum(
            1
            for position in masks
            if position <= len(sequence) and sequence[position - 1] != prompt[position - 1]
        )
        info.update(
            {
                "prompt": prompt,
                "generated_sequence": info["sequence"],
                "n_residues": len(sequence),
                "n_masked": len(masks),
                "n_changed": changed,
                "seed": seed,
                "temperature": temperature,
                "num_steps": num_steps,
                "model": str(params.get("model", _DEFAULT_MODEL)),
            }
        )
        form.info.update(info)
        out_name = str(params.get("output", "generation"))
        ctx[out_name] = form
        self._export_data = {
            "dims": ["sequence", "position"],
            "labels": {"sequence": {"generated": 0}, "position": {str(i): i for i in range(len(sequence))}},
            "info": {key: value for key, value in info.items() if key != "missing_code"},
        }
        return form

    def export(self, ctx):
        return getattr(self, "_export_data", {})
