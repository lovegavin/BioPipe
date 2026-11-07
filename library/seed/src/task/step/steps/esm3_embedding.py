"""esm3_embedding: per-residue ESM-3 embeddings for protein sequences."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_MODELS = {"esm3-sm-open-v1": "esm3_sm_open_v1", "esm3_sm_open_v1": "esm3_sm_open_v1"}
_CACHE: dict[tuple[str, str], object] = {}


def load_model(name: str, device: str):
    """Load (and cache) an ESM-3 checkpoint."""

    key = (name, device)
    if key in _CACHE:
        return _CACHE[key]
    try:
        import torch
        from esm.models.esm3 import ESM3
    except ImportError:
        raise StepError(
            "esm3_embedding: the ESM-3 package is required; install it with "
            "'python -m pip install git+https://github.com/evolutionaryscale/esm.git'"
        ) from None
    try:
        model = ESM3.from_pretrained(name, device=torch.device(device))
    except Exception as exc:  # noqa: BLE001
        raise StepError(f"esm3_embedding: could not load '{name}': {exc}") from None
    model.eval()
    try:
        model = model.float()
    except Exception:  # noqa: BLE001 - bfloat16 checkpoints still work on some builds
        pass
    _CACHE[key] = model
    return model


def encode_batch(model, sequences: list[str], device: str) -> list[np.ndarray]:
    """Return per-residue embeddings (L, D) for each sequence."""

    import torch

    try:
        from esm.sdk.api import ESMProtein
    except ImportError:
        ESMProtein = None  # tests may inject a lightweight model

    values = []
    for sequence in sequences:
        protein = ESMProtein(sequence=sequence) if ESMProtein is not None else sequence
        tokens = model.encode(protein)
        with torch.no_grad():
            output = model.forward(sequence_tokens=tokens.sequence.unsqueeze(0))
        embeddings = output.embeddings
        if embeddings.ndim == 3:
            embeddings = embeddings[0]
        matrix = embeddings[1 : 1 + len(sequence)].detach().cpu().numpy()
        if matrix.shape[0] != len(sequence):
            raise StepError(
                "esm3_embedding: the model returned "
                f"{matrix.shape[0]} residue embeddings for {len(sequence)} residues"
            )
        values.append(np.asarray(matrix, dtype=np.float32))
    return values


class Esm3EmbeddingStep(Step):
    provider = "operon-core"
    parameters_file = "esm3_embedding.Esm3EmbeddingStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_embedding",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 蛋白嵌入",
        "description": (
            "Compute per-residue ESM-3 embeddings for protein sequences with the official "
            "EvolutionaryScale open model loaded from a local Hugging Face cache."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 3, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "esm3"},
        "dependencies": [],
        "dependency_imports": ["esm"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        if not sequences:
            raise StepError("esm3_embedding: the input holds no sequence")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_embedding: device must be 'cpu' or 'cuda'")
        name = _MODELS.get(str(params.get("model_name", "esm3-sm-open-v1")).lower())
        if name is None:
            raise StepError("esm3_embedding: model_name must be 'esm3-sm-open-v1'")
        model = load_model(name, device)
        matrices = encode_batch(model, sequences, device)
        width = matrices[0].shape[1]
        for matrix in matrices:
            if matrix.shape[1] != width:
                raise StepError("esm3_embedding: embeddings disagree in width")
        max_length = max(matrix.shape[0] for matrix in matrices)
        data = np.full((len(sequences), max_length, width), np.nan, dtype=np.float32)
        labels_sequence = {f"seq{index + 1}": index for index in range(len(sequences))}
        labels_position = {str(index): index for index in range(max_length)}
        for index, matrix in enumerate(matrices):
            data[index, : matrix.shape[0], :] = matrix
        out_name = str(params.get("output", "embeddings"))
        ctx[out_name] = Form(
            data=data.astype(np.float32),
            dims=["sequence", "position", "embedding"],
            labels={
                "sequence": labels_sequence,
                "position": labels_position,
                "embedding": {f"e{index}": index for index in range(width)},
            },
            info={
                "missing_code": np.nan,
                "model": name,
                "device": device,
                "embedding_dim": int(width),
                "n_sequences": len(sequences),
                "lengths": [len(sequence) for sequence in sequences],
            },
        )
        mean = np.mean([matrix.mean() for matrix in matrices])
        self._export_data = {"model": name, "n_sequences": len(sequences), "embedding_dim": int(width), "mean": float(mean)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
