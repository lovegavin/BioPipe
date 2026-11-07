"""Design sequences against a backbone with the official ESM-IF1 model."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.context.base import Context

from ._esm_if_common import chain_residues, load_esm_if, native_sequence, residue_log_probs

_STATISTICS = ("mean_log_prob", "sequence_recovery")


class EsmIfDesignStep(Step):
    """Sample protein sequences for a fixed backbone with the official ESM-IF1 model."""

    provider = "operon-core"
    parameters_file = "esm_if_design.EsmIfDesignStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Design",
        "description": (
            "Sample sequences for a fixed protein backbone with the official ESM-IF1 "
            "inverse-folding model and score every design with the same model."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
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
        sample_dim = str(params.get("sample_dim", "sample"))
        chain = str(params.get("chain", "A") or "A").strip()
        model_path = params.get("model_path", "")
        raw_samples = params.get("num_samples", 4)
        num_samples = 4 if raw_samples is None else int(raw_samples)
        raw_temperature = params.get("temperature", 0.1)
        temperature = 0.1 if raw_temperature is None else float(raw_temperature)
        raw_seed = params.get("seed", 1)
        seed = 1 if raw_seed is None else int(raw_seed)
        out_name = str(params.get("output", "designs") or "designs")
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"esm_if_design: expected a structure form with dims [{atom_dim}, {field_dim}], "
                f"got {list(form.dims)}"
            )
        if num_samples < 1 or num_samples > 64:
            raise StepError("esm_if_design: num_samples must be between 1 and 64")
        if temperature <= 0:
            raise StepError("esm_if_design: temperature must be positive")
        labels, resnames, coords = chain_residues(form, field_dim, chain)
        native = native_sequence(resnames)
        model, alphabet, torch = load_esm_if(model_path, "esm_if_design")
        torch.manual_seed(seed)
        rows: list[list[float]] = []
        sequences: list[str] = []
        for _index in range(num_samples):
            sequence = model.sample(coords, temperature=temperature)
            if len(sequence) != len(labels):
                raise StepError(
                    f"esm_if_design: model returned {len(sequence)} residues for "
                    f"{len(labels)} backbone residues"
                )
            values = residue_log_probs(model, alphabet, coords, sequence)
            recovery = float(
                sum(1.0 for left, right in zip(sequence, native) if left == right) / len(native)
            )
            rows.append([float(np.mean(values)), recovery])
            sequences.append(sequence)
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[sample_dim, "statistic"],
            labels={
                sample_dim: {f"design{index + 1}": index for index in range(len(rows))},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "chain": chain,
                "model_path": str(model_path),
                "native_sequence": native,
                "sequences": sequences,
                "temperature": temperature,
                "seed": seed,
                "num_samples": num_samples,
                "metric": "mean_log_prob",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "chain": chain,
            "num_samples": len(rows),
            "temperature": temperature,
            "seed": seed,
            "sequences": sequences,
            "native_sequence": native,
            "mean_recovery": round(float(np.mean(data[:, 1])), 6),
            "mean_log_prob": round(float(np.mean(data[:, 0])), 6),
        }
        print(
            f"[esm_if_design] chain {chain}: {len(labels)} residues, {len(rows)} designs, "
            f"mean recovery {float(np.mean(data[:, 1])):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
