"""Shared lazy loading and tokenization for the ESM sequence operators."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import StepError

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
MAX_RESIDUES = 1022


def load_esm(model_path: str, device: str, operator: str):
    """Load a local ESM checkpoint and return (model, alphabet, torch, device)."""
    text = str(model_path or "").strip()
    if not text:
        raise StepError(
            f"{operator}: model_path is required; point it at a local ESM "
            "checkpoint such as esm2_t6_8M_UR50D.pt"
        )
    path = Path(text).expanduser()
    if not path.is_file():
        raise StepError(f"{operator}: model_path '{path}' is not a file")
    resolved = str(device or "cpu").strip().lower()
    if resolved not in ("cpu", "cuda"):
        raise StepError(f"{operator}: device must be 'cpu' or 'cuda'")
    try:
        import esm
        import torch
    except ImportError as error:  # pragma: no cover - dependency guard
        raise StepError(
            f"{operator}: fair-esm and torch are required to load a local "
            f"checkpoint ({error})"
        ) from error
    if resolved == "cuda" and not torch.cuda.is_available():
        raise StepError(
            f"{operator}: device 'cuda' requested but CUDA is not available"
        )
    model, alphabet = _load_checkpoint(path, esm, torch, operator)
    model = model.to(resolved)
    model.eval()
    return model, alphabet, torch, resolved


def _load_checkpoint(path: Path, esm, torch, operator: str):
    """Load a local ESM checkpoint.

    fair-esm 2.0.0 calls ``torch.load`` without ``weights_only``; torch 2.6
    changed the default and rejects the checkpoint's ``argparse.Namespace``.
    The official loader is tried first, then the checkpoint is read with the
    legacy unsafe loader (the file is a trusted local checkpoint) and handed
    to the same official model builder.
    """
    try:
        return esm.pretrained.load_model_and_alphabet_local(str(path))
    except Exception as error:  # noqa: BLE001 - message decides the fallback
        text = str(error)
        if "weights_only" not in text and "WeightsUnpickler" not in text:
            raise StepError(
                f"{operator}: cannot load ESM checkpoint '{path}': {error}"
            ) from error
    data = torch.load(str(path), map_location="cpu", weights_only=False)
    try:
        model, alphabet = esm.pretrained.load_model_and_alphabet_core(
            path.stem, data, None
        )
    except Exception as error:  # noqa: BLE001
        raise StepError(
            f"{operator}: cannot load ESM checkpoint '{path}': {error}"
        ) from error
    return model, alphabet


def sequence_tokens(alphabet, torch, sequence: str, device: str):
    """Tokenize one sequence as the ESM alphabet expects (BOS/EOS included)."""
    if not sequence:
        raise StepError("esm: sequence must not be empty")
    if len(sequence) > MAX_RESIDUES:
        raise StepError(
            "esm: sequence of length "
            f"{len(sequence)} exceeds the {MAX_RESIDUES}-residue context of "
            "the ESM2 checkpoints"
        )
    converter = alphabet.get_batch_converter()
    _, _, tokens = converter([("sequence", sequence)])
    return tokens.to(device)


def sequence_embeddings(model, alphabet, torch, sequences, device):
    """Return the mean-pooled final-layer embedding of every sequence."""
    rows: list[np.ndarray] = []
    for sequence in sequences:
        tokens = sequence_tokens(alphabet, torch, sequence, device)
        with torch.no_grad():
            output = model(tokens, repr_layers=[model.num_layers])
        hidden = output["representations"][model.num_layers]
        residues = hidden[0, 1 : len(sequence) + 1]
        rows.append(residues.mean(dim=0).detach().cpu().numpy())
    return np.stack(rows).astype(np.float32)
