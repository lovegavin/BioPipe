"""Ring-system statistics from RDKit molecules."""

from __future__ import annotations

import numpy as np
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

STATISTICS = (
    "n_rings",
    "n_aromatic_rings",
    "n_ring_systems",
    "n_spiro_rings",
    "largest_ring",
    "mean_ring_size",
)


def ring_systems(molecule) -> tuple[int, int]:
    """Count fused ring systems and spiro links from the SSSR rings."""
    rings = [tuple(sorted(ring)) for ring in molecule.GetRingInfo().AtomRings()]
    if not rings:
        return 0, 0
    parent = list(range(len(rings)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    spiro = 0
    for first in range(len(rings)):
        for second in range(first + 1, len(rings)):
            shared = len(set(rings[first]) & set(rings[second]))
            if shared >= 2:
                union(first, second)
            elif shared == 1:
                spiro += 1
    systems = len({find(index) for index in range(len(rings))})
    return systems, spiro


def ring_row(molecule) -> list[float]:
    rings = [tuple(ring) for ring in molecule.GetRingInfo().AtomRings()]
    if not rings:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    aromatic = sum(
        1
        for ring in rings
        if all(molecule.GetAtomWithIdx(int(index)).GetIsAromatic() for index in ring)
    )
    systems, spiro = ring_systems(molecule)
    sizes = [len(ring) for ring in rings]
    return [
        float(len(rings)),
        float(aromatic),
        float(systems),
        float(spiro),
        float(max(sizes)),
        float(np.mean(sizes)),
    ]


class RdkitRingSystemsStep(Step):
    """Ring counts, fused systems and size statistics per molecule."""

    provider = "operon-core"
    parameters_file = "rdkit_ring_systems.RdkitRingSystemsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_ring_systems",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit ring systems",
        "description": (
            "Counts SSSR rings, aromatic rings, fused ring systems and spiro links, "
            "and reports the largest and mean ring size."
        ),
        "category": "Machine Learning",
        "icon": "CirclesThree",
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        out_name = str(params.get("output", "rings"))
        smiles = params.get("smiles")
        if not isinstance(smiles, str) or not smiles.strip():
            raise StepError(
                "rdkit_ring_systems: smiles is required; give one 'SMILES [name]' line "
                "per molecule"
            )
        molecules = build_molecules(smiles, "rdkit_ring_systems")
        rows = [ring_row(molecule) for _, molecule in molecules]
        labels = [name for name, _ in molecules]
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {
                    name: index for index, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(labels),
                "statistics": list(STATISTICS),
            },
        )
        out.validate()
        self._export_data = {
            "n_molecules": len(labels),
            "total_rings": int(np.sum(np.asarray(rows)[:, 0])),
            "molecules_with_rings": int(np.sum(np.asarray(rows)[:, 0] > 0)),
            "largest_ring": int(np.max(np.asarray(rows)[:, 4])),
        }
        ctx[out_name] = out
        print(
            f"[rdkit_ring_systems] {len(labels)} molecules, "
            f"{self._export_data['total_rings']} rings, "
            f"largest {self._export_data['largest_ring']}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
