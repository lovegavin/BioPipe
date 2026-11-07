"""Per-position sequence entropy from ESM-IF1 sampled designs."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.context.base import Context

from ._esm_common import AA_ORDER
from ._esm_if_common import chain_residues, load_esm_if, native_sequence

_STATISTICS = ("entropy_bits", "recovery", "max_frequency")
_UNKNOWN = -1


def design_counts(sequences: list[str], length: int) -> np.ndarray:
    """Count amino acids per position for a list of equal-length designs."""

    if not sequences:
        raise StepError("esm_if_position_entropy: at least one design is required")
    alphabet = {letter: index for index, letter in enumerate(AA_ORDER)}
    counts = np.zeros((length, len(AA_ORDER)), dtype=np.float64)
    for sequence in sequences:
        if len(sequence) != length:
            raise StepError(
                "esm_if_position_entropy: design length "
                f"{len(sequence)} does not match the backbone length {length}"
            )
        for position, residue in enumerate(sequence):
            index = alphabet.get(residue.upper(), _UNKNOWN)
            if index < 0:
                raise StepError(
                    "esm_if_position_entropy: design contains the non-standard residue "
                    f"'{residue}' at position {position + 1}"
                )
            counts[position, index] += 1.0
    return counts


def position_rows(counts: np.ndarray, native: str) -> list[list[float]]:
    """Compute entropy bits, native recovery and consensus frequency per position."""

    alphabet = {letter: index for index, letter in enumerate(AA_ORDER)}
    totals = counts.sum(axis=1)
    probabilities = counts / np.maximum(totals[:, None], 1.0)
    rows: list[list[float]] = []
    for position in range(counts.shape[0]):
        row = probabilities[position]
        positive = row[row > 0.0]
        entropy = float(-(positive * np.log2(positive)).sum())
        if position < len(native):
            recovery = float(row[alphabet.get(native[position].upper(), 0)])
        else:
            recovery = 0.0
        rows.append([entropy, recovery, float(row.max())])
    return rows


class EsmIfPositionEntropyStep(Step):
    """Estimate per-position sequence entropy by sampling ESM-IF1 designs."""

    provider = "operon-core"
    parameters_file = "esm_if_position_entropy.EsmIfPositionEntropyStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_position_entropy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Position Entropy",
        "description": (
            "Sample the official ESM-IF1 inverse-folding model for a fixed backbone and "
            "report per-position sequence entropy, native recovery and consensus frequency."
        ),
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": [
            "numpy>=1.24",
            "torch>=2.0",
            "fair-esm>=2.0",
            "biotite>=0.37",
        ],
        "dependency_imports": ["esm", "torch"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        position_dim = str(params.get("position_dim", "position"))
        chain = str(params.get("chain", "A") or "A").strip()
        model_path = params.get("model_path", "")
        raw_samples = params.get("num_samples", 16)
        num_samples = 16 if raw_samples is None else int(raw_samples)
        raw_temperature = params.get("temperature", 0.1)
        temperature = 0.1 if raw_temperature is None else float(raw_temperature)
        raw_seed = params.get("seed", 1)
        seed = 1 if raw_seed is None else int(raw_seed)
        out_name = str(params.get("output", "entropy") or "entropy")
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "esm_if_position_entropy: expected a structure form with dims "
                f"[{atom_dim}, {field_dim}], got {list(form.dims)}"
            )
        if num_samples < 2 or num_samples > 256:
            raise StepError(
                "esm_if_position_entropy: num_samples must be between 2 and 256"
            )
        if temperature <= 0:
            raise StepError("esm_if_position_entropy: temperature must be positive")
        if seed < 0:
            raise StepError("esm_if_position_entropy: seed must not be negative")
        labels, resnames, coords = chain_residues(form, field_dim, chain)
        native = native_sequence(resnames)
        model, _alphabet, torch = load_esm_if(model_path, "esm_if_position_entropy")
        torch.manual_seed(seed)
        sequences: list[str] = []
        for _index in range(num_samples):
            sequence = str(model.sample(coords, temperature=temperature))
            if len(sequence) != len(labels):
                raise StepError(
                    "esm_if_position_entropy: model returned "
                    f"{len(sequence)} residues for {len(labels)} backbone residues"
                )
            sequences.append(sequence)
        counts = design_counts(sequences, len(labels))
        rows = position_rows(counts, native)
        data = np.asarray(rows, dtype=np.float32)
        if not np.isfinite(data).all():
            raise StepError(
                "esm_if_position_entropy: the entropy table contains non-finite values"
            )
        consensus = [
            AA_ORDER[int(np.argmax(counts[position]))] for position in range(len(labels))
        ]
        out = Form(
            data=data,
            dims=[position_dim, "statistic"],
            labels={
                position_dim: {str(index + 1): index for index in range(len(rows))},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "chain": chain,
                "model_path": str(model_path),
                "native_sequence": native,
                "consensus": "".join(consensus),
                "sequences": sequences,
                "num_samples": num_samples,
                "temperature": temperature,
                "seed": seed,
                "aa_order": AA_ORDER,
                "mean_entropy_bits": float(data[:, 0].mean()),
                "mean_recovery": float(data[:, 1].mean()),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "chain": chain,
            "num_samples": num_samples,
            "temperature": temperature,
            "seed": seed,
            "consensus": "".join(consensus),
            "native_sequence": native,
            "mean_entropy_bits": round(float(data[:, 0].mean()), 6),
            "mean_recovery": round(float(data[:, 1].mean()), 6),
            "most_variable": [
                str(index + 1)
                for index in np.argsort(-data[:, 0])[:5].tolist()
            ],
        }
        print(
            f"[esm_if_position_entropy] chain {chain}: {len(rows)} positions, "
            f"{num_samples} designs, mean entropy {float(data[:, 0].mean()):.3f} bits"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
