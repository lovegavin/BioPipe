"""Partial redesign of a protein backbone with the official ESM-IF model."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._esm_if_common import (
    chain_residues,
    load_esm_if,
    native_sequence,
    residue_log_probs,
    validate_sequence,
)
from src.task.step.steps.esm_if_mutation_scan import parse_positions

_STATISTICS = ("mean_log_prob", "designed_recovery", "n_designed")


def _fixed_partial(sequence: str, design_positions: list[int]) -> list[str]:
    """Return the ESM-IF partial sequence with mask tokens at design positions."""
    partial = list(sequence)
    for position in design_positions:
        partial[position] = "<mask>"
    return partial


def designed_recovery(native: str, designed: str, design_positions: list[int]) -> float:
    """Return the fraction of designed positions that recovered the native residue."""
    if not design_positions:
        return float("nan")
    matches = sum(1 for position in design_positions if designed[position] == native[position])
    return matches / len(design_positions)


class EsmIfRedesignStep(Step):
    provider = "operon-core"
    parameters_file = "esm_if_redesign.EsmIfRedesignStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_redesign",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Partial Redesign",
        "description": (
            "Redesign selected positions of a protein backbone with the official ESM-IF "
            "inverse-folding model while keeping the remaining residues fixed, then score "
            "every sampled sequence under the same model."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim", "default": "atom"}, {"param": "field_dim", "default": "field"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "encoders": {"type": "object", "optional": True},
                    },
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
        "dependencies": ["numpy>=1.24", "torch>=2.0", "fair-esm>=2.0", "biotite>=0.37"],
        "dependency_imports": ["numpy", "torch", "esm", "biotite"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        form = inputs[0] if inputs else None
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        if form is None or len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"esm_if_redesign: a structure form with dims [{atom_dim}, {field_dim}] is required"
            )
        model_path = str(params.get("model_path", "")).strip()
        position_text = str(params.get("design_positions", ""))
        chain = str(params.get("chain", "A")).strip()
        temperature = float(params.get("temperature", 0.1))
        if not 0.01 <= temperature <= 2.0:
            raise StepError("esm_if_redesign: temperature must be in [0.01, 2.0]")
        num_samples = int(params.get("num_samples", 4))
        if not 1 <= num_samples <= 16:
            raise StepError("esm_if_redesign: num_samples must be between 1 and 16")
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError("esm_if_redesign: seed must not be negative")
        output = str(params.get("output", "output"))

        labels, residue_names, coords = chain_residues(form, field_dim, chain)
        sequence = native_sequence(residue_names)
        validate_sequence(sequence, len(labels), "esm_if_redesign")
        if not sequence:
            raise StepError("esm_if_redesign: the selected chain has no residues")
        design_positions = [position - 1 for position in parse_positions(position_text, len(sequence))]
        if not design_positions:
            raise StepError("esm_if_redesign: design_positions selected no residue")

        model, alphabet, torch = load_esm_if(model_path, "esm_if_redesign")
        partial = _fixed_partial(sequence, design_positions)
        records: list[dict] = []
        for sample in range(1, num_samples + 1):
            torch.manual_seed(seed + sample - 1)
            designed = model.sample(coords, partial_seq=partial, temperature=temperature)
            designed = str(designed).strip()
            if len(designed) != len(sequence):
                raise StepError(
                    f"esm_if_redesign: sample {sample} returned {len(designed)} residues for a "
                    f"{len(sequence)}-residue chain"
                )
            log_probs = residue_log_probs(model, alphabet, coords, designed)
            records.append(
                {
                    "sample": sample,
                    "mean_log_prob": float(np.mean(log_probs)),
                    "designed_recovery": designed_recovery(sequence, designed, design_positions),
                    "n_designed": float(len(design_positions)),
                    "sequence": designed,
                }
            )

        data = np.asarray(
            [[record[name] for name in _STATISTICS] for record in records], dtype=np.float32
        )
        design_labels = [f"sample{record['sample']}" for record in records]
        out = Form(
            data=data,
            dims=["sample", "statistic"],
            labels={
                "sample": {label: index for index, label in enumerate(design_labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequences": [record["sequence"] for record in records],
                "native_sequence": sequence,
                "design_positions": [position + 1 for position in design_positions],
                "fixed_positions": [
                    position + 1 for position in range(len(sequence)) if position not in set(design_positions)
                ],
                "chain": chain,
                "residue_labels": labels,
                "model_path": model_path,
                "temperature": temperature,
                "seed": seed,
                "metric": "mean_log_prob is the mean ESM-IF log probability, higher is better",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "samples": len(records),
            "mean_log_prob": float(np.mean(data[:, 0])),
            "mean_designed_recovery": float(np.nanmean(data[:, 1])),
            "native_sequence": sequence,
            "sequences": out.info["sequences"],
            "design_positions": out.info["design_positions"],
            "model_path": model_path,
        }
        print(
            f"[esm_if_redesign] {len(records)} samples, chain {chain}, "
            f"{len(design_positions)} design positions, mean log-prob {np.mean(data[:, 0]):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
