"""esm3_secondary_structure: ESM-3 secondary-structure track prediction."""

from __future__ import annotations

import tempfile

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_HELIX = {"H", "G", "I"}
_STRAND = {"E", "B"}
_ALPHABET = " -HBEGITS"
_CACHE: dict[tuple[str, str], object] = {}


def state_code(letter: str) -> int:
    """Map a DSSP letter onto 0 helix, 1 strand, 2 coil."""

    if letter in _HELIX:
        return 0
    if letter in _STRAND:
        return 1
    return 2


def clean_structure(text: str, length: int) -> str:
    """Normalise a predicted track to one letter per residue."""

    cleaned = "".join(char if char in _ALPHABET else " " for char in str(text))
    if len(cleaned) > length:
        cleaned = cleaned[:length]
    if len(cleaned) < length:
        cleaned = cleaned + " " * (length - len(cleaned))
    return cleaned


def ss_summary(text: str) -> dict:
    """Count helix, strand and coil positions."""

    codes = [state_code(char) for char in text]
    counts = [codes.count(0), codes.count(1), codes.count(2)]
    n = max(len(codes), 1)
    return {
        "n_residues": len(codes),
        "n_helix": counts[0],
        "n_strand": counts[1],
        "n_coil": counts[2],
        "helix_fraction": counts[0] / n,
        "strand_fraction": counts[1] / n,
        "coil_fraction": counts[2] / n,
    }


def load_model(name: str, device: str):
    """Load an ESM-3 checkpoint once per (name, device)."""

    key = (name, device)
    if key in _CACHE:
        return _CACHE[key]
    try:
        import torch
        from esm.models.esm3 import ESM3
    except Exception as exc:  # noqa: BLE001
        raise StepError(
            "esm3_secondary_structure: the ESM package is required; install it with "
            "'pip install \"esm @ git+https://github.com/evolutionaryscale/esm.git\"'"
        ) from exc
    model = ESM3.from_pretrained(name, device=torch.device(device))
    model.eval()
    model.float()
    _CACHE[key] = model
    return model


def predict_secondary_structure(model, sequence: str, *, num_steps: int) -> str:
    """Generate the secondary-structure track for one sequence."""

    from esm.sdk.api import ESMProtein, GenerationConfig

    protein = ESMProtein(sequence=sequence)
    config = GenerationConfig(track="secondary_structure", num_steps=int(num_steps))
    result = model.generate(protein, config)
    text = getattr(result, "secondary_structure", None)
    if not text:
        raise StepError("esm3_secondary_structure: ESM-3 returned an empty secondary-structure track")
    return clean_structure(text, len(sequence))


class Esm3SecondaryStructureStep(Step):
    provider = "operon-core"
    parameters_file = "esm3_secondary_structure.Esm3SecondaryStructureStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_secondary_structure",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 secondary structure prediction",
        "description": "Predict DSSP-style secondary structure for one protein sequence with the ESM-3 secondary-structure track.",
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory", "environment": "esm3"},
        "dependencies": [],
        "dependency_imports": ["esm", "torch"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], params.get("sequence_dim", "sequence"), params.get("position_dim", "position"))
        if len(sequences) != 1:
            raise StepError(f"esm3_secondary_structure: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        if not sequence:
            raise StepError("esm3_secondary_structure: the sequence is empty")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_secondary_structure: device must be 'cpu' or 'cuda'")
        num_steps = int(params.get("num_steps", 8))
        if num_steps < 1:
            raise StepError("esm3_secondary_structure: num_steps must be at least 1")
        model_name = str(params.get("model_name", "esm3_sm_open_v1"))
        model = load_model(model_name, device)
        predicted = predict_secondary_structure(model, sequence, num_steps=num_steps)
        summary = ss_summary(predicted)

        report_dim = str(params.get("report_dim", "residue"))
        labels = {report_dim: {f"1:{index + 1}": index for index in range(len(predicted))}}
        data = np.array(
            [
                [float(state_code(char)), 1.0 if char in _HELIX else 0.0, 1.0 if char in _STRAND else 0.0, 1.0 if state_code(char) == 2 else 0.0]
                for char in predicted
            ],
            dtype=np.float32,
        )
        columns = ["state_code", "is_helix", "is_strand", "is_coil"]
        out = params.get("output", "ss")
        ctx[out] = Form(
            data=data,
            dims=[report_dim, "statistic"],
            labels={**labels, "statistic": {name: index for index, name in enumerate(columns)}},
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "predicted": predicted,
                "model_name": model_name,
                "num_steps": num_steps,
                **{key: float(value) if isinstance(value, float) else int(value) for key, value in summary.items()},
            },
        )
        self._export_data = {
            "output": out,
            "n_residues": int(summary["n_residues"]),
            **{key: float(value) for key, value in summary.items() if isinstance(value, float)},
        }
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
