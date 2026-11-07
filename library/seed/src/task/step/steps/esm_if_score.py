"""Score a sequence against a backbone with the official ESM-IF1 model."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.context.base import Context

from ._esm_if_common import (
    chain_residues,
    load_esm_if,
    native_sequence,
    residue_log_probs,
    validate_sequence,
)

_STATISTICS = ("log_prob",)


class EsmIfScoreStep(Step):
    """Score every residue of a chain with the official ESM-IF1 inverse-folding model."""

    provider = "operon-core"
    parameters_file = "esm_if_score.EsmIfScoreStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_if_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM-IF Score",
        "description": (
            "Score a protein chain with the official ESM-IF1 inverse-folding model and report "
            "the per-residue log probability of the observed sequence given the backbone."
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
        residue_dim = str(params.get("residue_dim", "residue"))
        chain = str(params.get("chain", "A") or "A").strip()
        model_path = params.get("model_path", "")
        sequence_text = str(params.get("sequence", "") or "").strip()
        out_name = str(params.get("output", "residue_scores") or "residue_scores")
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"esm_if_score: expected a structure form with dims [{atom_dim}, {field_dim}], "
                f"got {list(form.dims)}"
            )
        labels, resnames, coords = chain_residues(form, field_dim, chain)
        native = native_sequence(resnames)
        sequence = validate_sequence(sequence_text, len(labels), "esm_if_score") or native
        model, alphabet, _torch = load_esm_if(model_path, "esm_if_score")
        values = residue_log_probs(model, alphabet, coords, sequence)
        data = np.asarray(values, dtype=np.float32).reshape(-1, 1)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "chain": chain,
                "model_path": str(model_path),
                "sequence": sequence,
                "native_sequence": native,
                "n_residues": len(labels),
                "mean_log_prob": float(np.mean(values)),
                "total_log_prob": float(np.sum(values)),
                "metric": "log_prob",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "chain": chain,
            "n_residues": len(labels),
            "sequence": sequence,
            "mean_log_prob": round(float(np.mean(values)), 6),
            "total_log_prob": round(float(np.sum(values)), 6),
            "native": sequence == native,
        }
        print(
            f"[esm_if_score] chain {chain}: {len(labels)} residues, "
            f"mean log prob {float(np.mean(values)):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
