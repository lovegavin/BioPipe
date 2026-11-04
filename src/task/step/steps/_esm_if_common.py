"""Shared helpers for the ESM-IF1 inverse-folding operators."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError

from ._protein_common import decode_column, residue_labels
from ._structure_common import atom_coords

_BACKBONE = {"N": 0, "CA": 1, "C": 2}


def load_esm_if(model_path, operator: str):
    """Load a local ESM-IF1 checkpoint and return (model, alphabet, torch)."""
    raw = str(model_path or "").strip()
    if not raw:
        raise StepError(
            f"{operator}: model_path is required; point it at a local ESM-IF1 checkpoint "
            "such as esm_if1_gvp4_t16_142M_UR50.pt"
        )
    path = Path(raw)
    if not path.is_file():
        raise StepError(f"{operator}: model_path {str(path)!r} is not a file")
    try:
        import biotite.structure as biotite_structure
        import esm
        import torch
    except ImportError as error:  # pragma: no cover - dependency error path
        raise StepError(
            f"{operator}: fair-esm and torch are required for ESM-IF inference ({error})"
        ) from error
    if not hasattr(biotite_structure, "filter_backbone") and hasattr(
        biotite_structure, "filter_peptide_backbone"
    ):
        # biotite >= 2.0 renamed the helper; fair-esm still imports the old name.
        biotite_structure.filter_backbone = biotite_structure.filter_peptide_backbone
    try:
        model, alphabet = esm.pretrained.load_model_and_alphabet_local(str(path))
    except Exception as error:  # noqa: BLE001 - checkpoint loading failure
        if "WeightsUnpickler" not in str(error) and "weights_only" not in str(error):
            raise StepError(f"{operator}: cannot load ESM-IF checkpoint ({error})") from error
        # fair-esm stores an argparse.Namespace next to the weights, which
        # torch>=2.6 rejects under the default weights_only=True.
        try:
            payload = torch.load(str(path), map_location="cpu", weights_only=False)
            model, alphabet = esm.pretrained.load_model_and_alphabet_core(
                path.stem, payload, None
            )
        except Exception as fallback_error:  # noqa: BLE001
            raise StepError(
                f"{operator}: cannot load ESM-IF checkpoint ({fallback_error})"
            ) from fallback_error
    model.eval()
    return model, alphabet, torch


def _three_to_one(resname: str) -> str:
    from Bio.PDB.Polypeptide import protein_letters_3to1

    table = protein_letters_3to1
    key = str(resname).strip().upper()
    if key in table:
        return table[key]
    raise StepError(f"esm_if: residue '{key}' is not a standard amino acid")


def chain_residues(form, field_dim: str, chain: str):
    """Return (labels, resnames, backbone coords) for one chain."""
    chains = np.asarray(
        [str(item) for item in decode_column(form, field_dim, "chain")], dtype=object
    )
    resnames = np.asarray(
        [str(item).strip().upper() for item in decode_column(form, field_dim, "resname")],
        dtype=object,
    )
    names = np.asarray(
        [str(item).strip() for item in decode_column(form, field_dim, "atom_name")], dtype=object
    )
    labels = residue_labels(form, field_dim)
    coords = atom_coords(form, field_dim)
    mask = chains == chain
    if not mask.any():
        raise StepError(f"esm_if: chain '{chain}' was not found in the structure form")
    order = list(dict.fromkeys(labels[mask].tolist()))
    index = {label: position for position, label in enumerate(order)}
    backbone = np.full((len(order), 3, 3), np.nan, dtype=np.float32)
    first_resname: dict[str, str] = {}
    for label, name, xyz, resname in zip(labels[mask], names[mask], coords[mask], resnames[mask]):
        first_resname.setdefault(label, resname)
        slot = _BACKBONE.get(name.upper())
        if slot is not None:
            backbone[index[label], slot] = xyz
    incomplete = np.isnan(backbone).any(axis=(1, 2))
    if incomplete.any():
        bad = order[int(np.argmax(incomplete))]
        raise StepError(
            f"esm_if: residue {bad} of chain '{chain}' has no complete N/CA/C backbone"
        )
    residue_names = [first_resname[label] for label in order]
    return order, residue_names, backbone


def native_sequence(residue_names) -> str:
    return "".join(_three_to_one(name) for name in residue_names)


def validate_sequence(text: str, length: int, operator: str) -> str:
    sequence = str(text or "").strip().upper()
    if not sequence:
        return ""
    if len(sequence) != length:
        raise StepError(
            f"{operator}: sequence length {len(sequence)} does not match the "
            f"{length} backbone residues"
        )
    for index, residue in enumerate(sequence):
        if residue not in "ACDEFGHIKLMNPQRSTVWY":
            raise StepError(
                f"{operator}: sequence position {index + 1} ('{residue}') is not a "
                "standard amino acid"
            )
    return sequence


def residue_log_probs(model, alphabet, coords, sequence: str):
    """Per-residue log probability of ``sequence`` under the backbone model."""
    from esm.inverse_folding.util import get_sequence_loss

    loss, padding = get_sequence_loss(model, alphabet, coords, sequence)
    keep = ~np.asarray(padding, dtype=bool)
    values = -np.asarray(loss, dtype=np.float32)
    length = len(sequence)
    if keep.shape[0] < length:
        raise StepError("esm_if: the model returned fewer scores than residues")
    values = values[:length]
    keep = keep[:length]
    if not keep.all():
        bad = int(np.argmin(keep))
        raise StepError(f"esm_if: the model did not score residue {bad + 1}")
    return values
