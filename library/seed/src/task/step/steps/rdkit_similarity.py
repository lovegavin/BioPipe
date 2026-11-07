"""Pairwise molecular similarity from Morgan fingerprints."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules


def similarity_function(metric: str):
    from rdkit import DataStructs

    table = {
        "tanimoto": DataStructs.TanimotoSimilarity,
        "dice": DataStructs.DiceSimilarity,
        "cosine": DataStructs.CosineSimilarity,
    }
    return table[metric]


class RdkitSimilarityStep(Step):
    """Symmetric similarity matrix across a molecule set."""

    provider = 'operon-core'
    parameters_file = 'rdkit_similarity.RdkitSimilarityStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdkit_similarity',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Molecular similarity matrix',
        'description': (
            'Parse a list of SMILES, build Morgan fingerprints and report the '
            'pairwise Tanimoto, Dice or cosine similarity as a symmetric '
            'molecule-by-molecule matrix.'
        ),
        'category': 'Machine Learning',
        'icon': 'GridNine',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                },
            },
        },
        'resources': {
            'memory_modes': ['full'],
            'supports_cuda': False,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24', 'rdkit>=2022.9'],
        'dependency_imports': ['rdkit'],
        'inputs_arity': 0,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        comparison_dim = str(params.get("comparison_dim", "molecule_b")).strip() or "molecule_b"
        radius = int(params.get("radius", 2))
        n_bits = int(params.get("n_bits", 2048))
        use_features = bool(params.get("use_features", False))
        metric = str(params.get("metric", "tanimoto")).strip().lower()
        out_name = params.get("output", self.name)

        if not 1 <= radius <= 6:
            raise StepError("rdkit_similarity: radius must be between 1 and 6")
        if not 64 <= n_bits <= 16384:
            raise StepError("rdkit_similarity: n_bits must be between 64 and 16384")
        if metric not in ("tanimoto", "dice", "cosine"):
            raise StepError("rdkit_similarity: metric must be 'tanimoto', 'dice' or 'cosine'")
        if molecule_dim == comparison_dim:
            raise StepError(
                "rdkit_similarity: molecule_dim and comparison_dim must be different dims"
            )

        molecules = build_molecules(params.get("smiles", ""), "rdkit_similarity")
        from rdkit.Chem import rdMolDescriptors

        fingerprints = [
            rdMolDescriptors.GetMorganFingerprintAsBitVect(
                molecule, radius, nBits=n_bits, useFeatures=use_features
            )
            for _name, molecule in molecules
        ]
        compare = similarity_function(metric)
        count = len(fingerprints)
        data = np.zeros((count, count), dtype=np.float32)
        for row in range(count):
            for column in range(row, count):
                value = float(compare(fingerprints[row], fingerprints[column]))
                data[row, column] = value
                data[column, row] = value

        label_list = [name for name, _molecule in molecules]
        labels = {label: index for index, label in enumerate(label_list)}
        form_out = Form(
            data=data,
            dims=[molecule_dim, comparison_dim],
            labels={molecule_dim: dict(labels), comparison_dim: dict(labels)},
            info={
                "molecules": label_list,
                "metric": metric,
                "radius": radius,
                "n_bits": n_bits,
                "use_features": use_features,
                "n_molecules": count,
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_molecules": count,
            "metric": metric,
            "radius": radius,
            "n_bits": n_bits,
            "mean_similarity": round(
                float(data[np.triu_indices(count, k=1)].mean()) if count > 1 else 0.0, 6
            ),
        }
        print(
            f"[{self.name}] {count} molecules ({metric}, radius {radius}, "
            f"{n_bits} bits)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
