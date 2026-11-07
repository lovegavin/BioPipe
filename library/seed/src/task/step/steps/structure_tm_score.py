"""structure_tm_score: TM-score between a model and a reference structure."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels
from src.task.step.steps.structure_rmsd import kabsch

STATISTICS = ("tm_score", "rmsd", "aligned_fraction", "d0")


def d0_for_length(length: int) -> float:
    """Length-dependent TM-score scale."""

    if length <= 15:
        return 0.5
    return float(max(1.24 * (length - 15) ** (1.0 / 3.0) - 1.8, 0.5))


def ca_map(form: Form, field_dim: str, chains: str = "") -> dict[str, np.ndarray]:
    """Return resname:number -> C-alpha coordinates for the requested chains.

    The chain is deliberately excluded from the key so that independent copies of
    the same chain (for example ``A`` and ``B`` in 1MEL) can be matched.
    """

    labels = residue_labels(form, field_dim)
    names = decode_column(form, field_dim, "atom_name")
    elements = decode_column(form, field_dim, "element")
    if names is None:
        raise StepError("structure_tm_score: the structure form carries no 'atom_name' column")
    wanted = {chain.strip() for chain in chains.split(",") if chain.strip()} if chains else None
    mapping: dict[str, np.ndarray] = {}
    for index, label in enumerate(labels):
        chain = str(label).split(":")[0]
        if wanted is not None and chain not in wanted:
            continue
        atom = str(names[index]).strip().upper()
        element = str(elements[index]).strip().upper() if elements is not None else ""
        if atom in ("CA", "C1") or (atom == "CA" and element in ("C", "")):
            parts = str(label).split(":")
            key = ":".join(parts[1:]) if len(parts) >= 3 else str(label)
            if key in mapping:
                continue
            mapping[key] = np.asarray(form.data[index, :3], dtype=float)
    if not mapping:
        raise StepError("structure_tm_score: no C-alpha atoms were found for the requested chains")
    return mapping


def match_residues(model: dict[str, np.ndarray], reference: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Match residues by chain:number label and return the two coordinate arrays."""

    shared = sorted(
        set(model) & set(reference),
        key=lambda item: int("".join(char for char in str(item).split(":")[1] if char.isdigit()) or 0),
    )
    if len(shared) < 10:
        raise StepError(
            f"structure_tm_score: only {len(shared)} residues are shared between the two structures; at least 10 are required"
        )
    first = np.asarray([model[label] for label in shared], dtype=float)
    second = np.asarray([reference[label] for label in shared], dtype=float)
    return first, second, shared


def tm_score(mobile: np.ndarray, reference: np.ndarray, *, cutoff: float = 4.5, iterations: int = 30) -> tuple[float, float, float, float]:
    """Iteratively superpose and compute TM-score, RMSD, aligned fraction and d0."""

    length = len(mobile)
    d0 = d0_for_length(length)
    weights = np.ones(length, dtype=float)
    rotation = np.eye(3)
    translation = np.zeros(3)
    for _ in range(iterations):
        selected = weights > 0.5
        if selected.sum() < 3:
            break
        rotation, translation, _rmsd = kabsch(mobile[selected], reference[selected])
        moved = (rotation @ mobile.T).T + translation
        distances = np.linalg.norm(moved - reference, axis=1)
        new_weights = (distances < cutoff).astype(float)
        if np.array_equal(new_weights, weights):
            break
        weights = new_weights
    rotation, translation, rmsd = kabsch(mobile[weights > 0.5], reference[weights > 0.5]) if weights.sum() >= 3 else (rotation, translation, 0.0)
    moved = (rotation @ mobile.T).T + translation
    distances = np.linalg.norm(moved - reference, axis=1)
    score = float(np.sum(1.0 / (1.0 + (distances / d0) ** 2)) / length)
    aligned = float((distances < cutoff).mean())
    return score, float(rmsd), aligned, d0


class StructureTmScoreStep(Step):
    provider = "operon-core"
    parameters_file = "structure_tm_score.StructureTmScoreStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_tm_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "TM-score 结构相似度",
        "description": (
            "Superpose a model structure onto a reference by C-alpha atoms and report "
            "the length-normalised TM-score with iterative distance weighting."
        ),
        "category": "Structure",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_tm_score: the model form is empty")
        reference_path = str(params.get("reference_path", "")).strip()
        if not reference_path:
            raise StepError("structure_tm_score: reference_path is required")
        path = Path(reference_path).expanduser()
        if not path.is_file():
            raise StepError(f"structure_tm_score: reference_path {path} is not a file")
        reference = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
        field_dim = str(params.get("field_dim", "field"))
        mobile_map = ca_map(form, field_dim, str(params.get("model_chains", "")))
        reference_map = ca_map(reference, field_dim, str(params.get("reference_chains", "")))
        mobile, target, shared = match_residues(mobile_map, reference_map)
        score, rmsd, aligned, d0 = tm_score(mobile, target, cutoff=float(params.get("cutoff", 4.5)), iterations=int(params.get("iterations", 30)))
        statistics = {"tm_score": score, "rmsd": rmsd, "aligned_fraction": aligned, "d0": d0}
        output_dim = str(params.get("model_dim", "model"))
        out_name = str(params.get("output", "tm"))
        ctx[out_name] = Form(
            data=np.asarray([[statistics[name] for name in STATISTICS]], dtype=np.float32),
            dims=[output_dim, "statistic"],
            labels={output_dim: {str(params.get("model_label", "model")): 0}, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={"missing_code": np.nan, "n_residues": len(shared), "d0": d0, "residues": shared},
        )
        self._export_data = {"statistics": statistics, "n_residues": len(shared), "shared": shared}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
