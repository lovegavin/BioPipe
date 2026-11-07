"""structure_lddt: local Distance Difference Test against a reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels
from src.task.step.steps.structure_tm_score import ca_map, match_residues

THRESHOLDS = (0.5, 1.0, 2.0, 4.0)
STATISTICS = ("lddt", "n_pairs", "n_residues")


def lddt_scores(
    mobile: np.ndarray,
    reference: np.ndarray,
    *,
    cutoff: float = 15.0,
    exclude_same_residue: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Return per-atom lDDT and the number of scored pairs for each atom."""

    if mobile.shape != reference.shape:
        raise StepError("structure_lddt: the model and the reference must have the same number of atoms")
    count = mobile.shape[0]
    if count < 2:
        raise StepError("structure_lddt: at least two atoms are required")
    true_distances = np.linalg.norm(reference[:, None, :] - reference[None, :, :], axis=-1)
    pred_distances = np.linalg.norm(mobile[:, None, :] - mobile[None, :, :], axis=-1)
    mask = true_distances < cutoff
    if exclude_same_residue:
        np.fill_diagonal(mask, False)
    useful = np.abs(true_distances - pred_distances)
    scores = np.zeros(count, dtype=float)
    pair_counts = np.zeros(count, dtype=float)
    for index in range(count):
        selected = mask[index]
        pair_counts[index] = float(selected.sum())
        if not selected.any():
            scores[index] = float("nan")
            continue
        hits = np.zeros(int(pair_counts[index]), dtype=float)
        for threshold in THRESHOLDS:
            hits += (useful[index][selected] < threshold).astype(float)
        scores[index] = float((hits * 0.25).mean())
    return scores, pair_counts


def lddt_table(mobile: np.ndarray, reference: np.ndarray, labels: list[str], *, cutoff: float = 15.0) -> list[dict]:
    """Aggregate per-atom lDDT into per-residue rows."""

    scores, counts = lddt_scores(mobile, reference, cutoff=cutoff)
    rows = []
    for label, score, count in zip(labels, scores, counts):
        rows.append({"residue": label, "lddt": float(score), "n_pairs": float(count)})
    return rows


class StructureLddtStep(Step):
    provider = "operon-core"
    parameters_file = "structure_lddt.StructureLddtStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_lddt",
        "version": "1.0.0",
        "kind": "operator",
        "title": "lDDT 局部距离差异检验",
        "description": (
            "Compute per-residue local Distance Difference Test scores for a model "
            "against a reference structure using C-alpha atoms in a 15 A inclusion "
            "radius and the 0.5/1/2/4 A thresholds."
        ),
        "category": "Structure",
        "icon": "ChartLine",
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
            raise StepError("structure_lddt: the model form is empty")
        reference_path = str(params.get("reference_path", "")).strip()
        if not reference_path:
            raise StepError("structure_lddt: reference_path is required")
        path = Path(reference_path).expanduser()
        if not path.is_file():
            raise StepError(f"structure_lddt: reference_path {path} is not a file")
        reference = read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})
        field_dim = str(params.get("field_dim", "field"))
        mobile_map = ca_map(form, field_dim, str(params.get("model_chains", "")))
        reference_map = ca_map(reference, field_dim, str(params.get("reference_chains", "")))
        mobile, target, shared = match_residues(mobile_map, reference_map)
        rows = lddt_table(mobile, target, [str(label) for label in shared], cutoff=float(params.get("inclusion_cutoff", 15.0)))
        values = np.asarray([[row["lddt"], row["n_pairs"]] for row in rows], dtype=np.float32)
        finite = values[:, 0][np.isfinite(values[:, 0])]
        output_dim = str(params.get("residue_dim", "residue"))
        out_name = str(params.get("output", "lddt"))
        ctx[out_name] = Form(
            data=values,
            dims=[output_dim, "statistic"],
            labels={
                output_dim: {row["residue"]: index for index, row in enumerate(rows)},
                "statistic": {"lddt": 0, "n_pairs": 1},
            },
            info={
                "missing_code": np.nan,
                "mean_lddt": float(finite.mean()) if finite.size else 0.0,
                "n_residues": len(rows),
                "inclusion_cutoff": float(params.get("inclusion_cutoff", 15.0)),
                "thresholds": list(THRESHOLDS),
            },
        )
        self._export_data = {"rows": rows, "mean_lddt": float(finite.mean()) if finite.size else 0.0}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
