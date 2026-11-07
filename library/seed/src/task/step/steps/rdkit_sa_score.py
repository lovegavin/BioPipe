"""Synthetic accessibility scores computed with the official RDKit scorer."""

from __future__ import annotations

import os
import sys

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = ("sa_score",)
_CLASS_BOUNDS = ((3.0, "easy"), (5.0, "moderate"), (7.0, "hard"))


def _scorer():
    try:
        from rdkit import RDConfig
    except ImportError as error:  # pragma: no cover - dependency gate
        raise StepError("rdkit_sa_score: the RDKit package is required") from error
    contrib = os.path.join(RDConfig.RDContribDir, "SA_Score")
    if contrib not in sys.path:
        sys.path.append(contrib)
    import sascorer  # type: ignore

    return sascorer


def sa_class(score: float) -> str:
    """Bucket a synthetic accessibility score using Ertl's usual thresholds."""
    for bound, name in _CLASS_BOUNDS:
        if score < bound:
            return name
    return "very hard"


def sa_score(molecule) -> float:
    """Return the Ertl synthetic accessibility score for one RDKit molecule."""
    if molecule.GetNumHeavyAtoms() == 0:
        raise StepError("rdkit_sa_score: cannot score a molecule without heavy atoms")
    value = float(_scorer().calculateScore(molecule))
    if not np.isfinite(value):
        raise StepError("rdkit_sa_score: the scorer produced a non-finite value")
    return value


class RdkitSaScoreStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_sa_score.RdkitSaScoreStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_sa_score",
        "kind": "operator",
        "version": "1.0.0",
        "title": "RDKit Synthetic Accessibility",
        "description": (
            "Score molecules with Ertl's synthetic accessibility model from the official "
            "RDKit contribution scorer, with an easy/moderate/hard/very-hard bucket."
        ),
        "category": "Machine Learning",
        "icon": "Scales",
        "contracts": {
            "version": 1,
            "inputs": [],
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
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["numpy", "rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        text = str(params.get("smiles", ""))
        molecules = build_molecules(text, "rdkit_sa_score")
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        output = str(params.get("output", "output"))

        scores = [sa_score(molecule) for _, molecule in molecules]
        data = np.asarray([[value] for value in scores], dtype=np.float32)
        labels = molecule_labels([name for name, _ in molecules], molecule_dim)
        out = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(molecules),
                "molecules": [name for name, _ in molecules],
                "smiles": [smiles for _, smiles in parse_smiles_text(text, "rdkit_sa_score")],
                "classes": [sa_class(value) for value in scores],
                "score_range": [1.0, 10.0],
                "buckets": {
                    "easy": "< 3.0",
                    "moderate": "< 5.0",
                    "hard": "< 7.0",
                    "very hard": ">= 7.0",
                },
                "model": "ertl-sascorer",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "scores": [round(value, 4) for value in scores],
            "classes": out.info["classes"],
            "mean_score": float(np.mean(scores)),
        }
        print(
            f"[rdkit_sa_score] {len(molecules)} molecules, "
            f"mean SA {np.mean(scores):.3f}, hardest {sa_class(max(scores))}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
