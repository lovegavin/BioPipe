"""esm3_sasa_prediction: per-residue solvent accessibility from the ESM-3 SASA track."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_CACHE: dict[tuple[str, str], object] = {}


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
            "esm3_sasa_prediction: the ESM package is required; install it with "
            "'pip install \"esm @ git+https://github.com/evolutionaryscale/esm.git\"'"
        ) from exc
    model = ESM3.from_pretrained(name, device=torch.device(device))
    model.eval()
    model.float()
    _CACHE[key] = model
    return model


def normalise_sasa(values, length: int) -> np.ndarray:
    """Coerce a generated SASA track into one finite float per residue."""

    if hasattr(values, "detach"):
        values = values.detach().cpu().numpy()
    array = np.asarray(values, dtype=np.float64).reshape(-1)
    if array.size == 0:
        raise StepError("esm3_sasa_prediction: ESM-3 returned an empty SASA track")
    if array.size > length:
        array = array[:length]
    if array.size < length:
        array = np.concatenate([array, np.full(length - array.size, np.nan)])
    return array


def predict_sasa(model, sequence: str, *, num_steps: int) -> np.ndarray:
    """Generate the SASA track for one sequence."""

    from esm.sdk.api import ESMProtein, GenerationConfig

    protein = ESMProtein(sequence=sequence)
    config = GenerationConfig(track="sasa", num_steps=int(num_steps))
    result = model.generate(protein, config)
    values = getattr(result, "sasa", None)
    if values is None:
        raise StepError("esm3_sasa_prediction: ESM-3 returned no SASA track")
    return normalise_sasa(values, len(sequence))


class Esm3SasaPredictionStep(Step):
    provider = "operon-core"
    parameters_file = "esm3_sasa_prediction.Esm3SasaPredictionStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm3_sasa_prediction",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-3 solvent accessibility prediction",
        "description": "Predict per-residue solvent-accessible surface area for one protein sequence with the ESM-3 SASA track.",
        "category": "Machine Learning",
        "icon": "Waves",
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
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
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
            raise StepError(f"esm3_sasa_prediction: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        if not sequence:
            raise StepError("esm3_sasa_prediction: the sequence is empty")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("esm3_sasa_prediction: device must be 'cpu' or 'cuda'")
        num_steps = int(params.get("num_steps", 8))
        if num_steps < 1:
            raise StepError("esm3_sasa_prediction: num_steps must be at least 1")
        model_name = str(params.get("model_name", "esm3_sm_open_v1"))
        model = load_model(model_name, device)
        values = predict_sasa(model, sequence, num_steps=num_steps)
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            raise StepError("esm3_sasa_prediction: the SASA track carries no finite value")

        report_dim = str(params.get("report_dim", "residue"))
        labels = {report_dim: {f"1:{index + 1}": index for index in range(len(values))}}
        data = np.array([[value, 1.0 if value >= 25.0 else 0.0] for value in values], dtype=np.float32)
        out = params.get("output", "sasa")
        ctx[out] = Form(
            data=data,
            dims=[report_dim, "statistic"],
            labels={**labels, "statistic": {"predicted_sasa": 0, "is_exposed": 1}},
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "model_name": model_name,
                "num_steps": num_steps,
                "mean_sasa": float(finite.mean()),
                "min_sasa": float(finite.min()),
                "max_sasa": float(finite.max()),
                "n_residues": int(finite.size),
                "displayed_fraction": float((finite >= 25.0).mean()),
            },
        )
        self._export_data = {
            "output": out,
            "n_residues": int(finite.size),
            "mean_sasa": float(finite.mean()),
            "displayed_fraction": float((finite >= 25.0).mean()),
        }
        return ctx[out]

    def export(self, ctx):
        return getattr(self, "_export_data", {})
