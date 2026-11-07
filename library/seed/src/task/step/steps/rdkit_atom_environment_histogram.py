"""Hashed atom-environment histograms per molecule."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

STATISTICS = ("n_environments", "n_unique", "top_count", "entropy")


def environment_counts(molecule, radius: int) -> dict[int, int]:
    from rdkit.Chem import AllChem

    fingerprint = AllChem.GetMorganFingerprint(molecule, radius, useCounts=True)
    return dict(fingerprint.GetNonzeroElements())


def environment_row(molecule, radius: int) -> dict:
    counts = environment_counts(molecule, radius)
    total = int(sum(counts.values()))
    if total == 0:
        return {"n_environments": 0.0, "n_unique": 0.0, "top_count": 0.0, "entropy": 0.0,
                "_counts": {}, "_total": 0}
    values = np.asarray(list(counts.values()), dtype=np.float64)
    probabilities = values / total
    return {
        "n_environments": float(total),
        "n_unique": float(len(counts)),
        "top_count": float(values.max()),
        "entropy": float(-np.sum(probabilities * np.log2(probabilities))),
        "_counts": counts,
        "_total": total,
    }


class RdkitAtomEnvironmentHistogramStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_atom_environment_histogram.RdkitAtomEnvironmentHistogramStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_atom_environment_histogram",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Atom environment histogram",
        "description": "Counts hashed Morgan atom environments per molecule and reports entropy.",
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        smiles = str(params.get("smiles") or "")
        radius = int(params.get("radius", 2))
        molecule_dim = str(params.get("molecule_dim") or "molecule")
        out_name = str(params["output"])

        if not 1 <= radius <= 4:
            raise StepError("rdkit_atom_environment_histogram: radius must be between 1 and 4")
        molecules = build_molecules(smiles, "rdkit_atom_environment_histogram")
        rows = [environment_row(molecule, radius) for _, molecule in molecules]

        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        labels = {name: index for index, (name, _) in enumerate(molecules)}
        output = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={molecule_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "radius": radius,
                "n_molecules": len(rows),
                "environments": [
                    {"name": name, "counts": {int(key): int(value) for key, value in row["_counts"].items()},
                     "total": row["_total"]}
                    for (name, _), row in zip(molecules, rows)
                ],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_molecules": len(rows),
            "radius": radius,
            "mean_unique": float(np.mean([row["n_unique"] for row in rows])),
            "mean_entropy": float(np.mean([row["entropy"] for row in rows])),
        }
        print(
            f"[rdkit_atom_environment_histogram] {len(rows)} molecules, radius {radius}, "
            f"mean unique {self._export_data['mean_unique']:.1f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
