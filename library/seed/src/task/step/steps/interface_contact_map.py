"""Residue-pair contact map between two chain groups of a structure."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import decode_column, heavy_atom_mask, residue_labels, split_chains
from ._structure_common import atom_coords, field_columns, pick_chain_sides

_VALUES = ("binary", "min_distance")


def contact_pairs(
    binder_coords: np.ndarray,
    binder_residues: np.ndarray,
    target_coords: np.ndarray,
    target_residues: np.ndarray,
    cutoff: float,
) -> dict[tuple[int, int], float]:
    """Return the minimal atom-pair distance per contacting residue pair."""
    from scipy.spatial import cKDTree

    combined = np.vstack([binder_coords, target_coords])
    tree = cKDTree(combined)
    pairs = tree.query_pairs(r=cutoff, output_type="ndarray")
    n_binder = binder_coords.shape[0]
    best: dict[tuple[int, int], float] = {}
    for left, right in pairs:
        left = int(left)
        right = int(right)
        if left < n_binder <= right:
            binder_index = left
            target_index = right - n_binder
        elif right < n_binder <= left:
            binder_index = right
            target_index = left - n_binder
        else:
            continue
        distance = float(np.linalg.norm(combined[left] - combined[right]))
        key = (int(binder_residues[binder_index]), int(target_residues[target_index]))
        current = best.get(key)
        if current is None or distance < current:
            best[key] = distance
    return best


class InterfaceContactMapStep(Step):
    """Binder-by-target residue contact map from heavy-atom distances."""

    provider = 'operon-core'
    parameters_file = 'interface_contact_map.InterfaceContactMapStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'interface_contact_map',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Interface contact map',
        'description': (
            'Build a binder-residue by target-residue matrix from the heavy atoms '
            'of two chain groups: a binary contact map or the minimal atom-pair '
            'distance for every contacting residue pair.'
        ),
        'category': 'Machine Learning',
        'icon': 'GridNine',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'dims': [
                        {'param': 'atom_dim', 'default': 'atom'},
                        {'param': 'field_dim', 'default': 'field'},
                    ],
                    'labels': [],
                    'parallel': [],
                    'ndim': 2,
                }
            ],
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
        'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
        'dependency_imports': ['scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        row_dim = str(params.get("binder_dim", "binder_residue")).strip() or "binder_residue"
        col_dim = str(params.get("target_dim", "target_residue")).strip() or "target_residue"
        binder_text = str(params.get("binder_chains", "A"))
        target_text = str(params.get("target_chains", ""))
        cutoff = float(params.get("cutoff", 4.5))
        value = str(params.get("value", "binary")).strip().lower()
        exclude = split_chains(params.get("exclude_resnames", "HOH,WAT"))
        out_name = params.get("output", self.name)

        if row_dim == col_dim:
            raise StepError("interface_contact_map: binder_dim and target_dim must be different")
        if not 0.0 < cutoff <= 10.0:
            raise StepError("interface_contact_map: cutoff must be in (0, 10] angstrom")
        if value not in _VALUES:
            raise StepError("interface_contact_map: value must be 'binary' or 'min_distance'")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "interface_contact_map: a PDB form with dims [atom, field] is required"
            )
        field_columns(form, field_dim, ["x", "y", "z", "chain", "resname", "residue_number"])

        chains = np.asarray(
            [str(item) for item in decode_column(form, field_dim, "chain")], dtype=object
        )
        resnames = np.asarray(
            [str(item) for item in decode_column(form, field_dim, "resname")], dtype=object
        )
        labels = residue_labels(form, field_dim)
        coords = atom_coords(form, field_dim)
        heavy = heavy_atom_mask(form, field_dim)
        keep = heavy & ~np.isin(resnames, exclude)
        if not keep.any():
            raise StepError("interface_contact_map: the PDB form has no heavy atoms to analyse")

        present = sorted({str(item).strip() for item in chains})
        binder, target = pick_chain_sides(
            present, binder_text, target_text, "interface_contact_map"
        )
        binder_mask = keep & np.isin(chains, binder)
        target_mask = keep & np.isin(chains, target)
        if not binder_mask.any():
            raise StepError("interface_contact_map: the binder chains have no heavy atoms")
        if not target_mask.any():
            raise StepError("interface_contact_map: the target chains have no heavy atoms")

        binder_labels = list(dict.fromkeys(labels[binder_mask].tolist()))
        target_labels = list(dict.fromkeys(labels[target_mask].tolist()))
        binder_index = {label: index for index, label in enumerate(binder_labels)}
        target_index = {label: index for index, label in enumerate(target_labels)}
        binder_residues = np.asarray(
            [binder_index[label] for label in labels[binder_mask]], dtype=np.int64
        )
        target_residues = np.asarray(
            [target_index[label] for label in labels[target_mask]], dtype=np.int64
        )

        best = contact_pairs(
            coords[binder_mask],
            binder_residues,
            coords[target_mask],
            target_residues,
            cutoff,
        )
        fill = 0.0 if value == "binary" else np.nan
        data = np.full((len(binder_labels), len(target_labels)), fill, dtype=np.float32)
        for (row, column), distance in best.items():
            data[row, column] = 1.0 if value == "binary" else distance

        pairs = [
            {
                "binder": binder_labels[row],
                "target": target_labels[column],
                "distance": round(float(distance), 4),
            }
            for (row, column), distance in sorted(best.items())
        ]
        form_out = Form(
            data=data,
            dims=[row_dim, col_dim],
            labels={
                row_dim: {label: index for index, label in enumerate(binder_labels)},
                col_dim: {label: index for index, label in enumerate(target_labels)},
            },
            info={
                "missing_code": np.nan,
                "n_contacts": len(pairs),
                "cutoff": cutoff,
                "value": value,
                "binder_chains": binder,
                "target_chains": target,
                "binder_residues": binder_labels,
                "target_residues": target_labels,
                "excluded_resnames": exclude,
                "pairs": pairs,
                "unit": "A",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_binder_residues": len(binder_labels),
            "n_target_residues": len(target_labels),
            "n_contacts": len(pairs),
            "binder_coverage": round(len({row for row, _ in best}) / len(binder_labels), 4),
            "target_coverage": round(len({column for _, column in best}) / len(target_labels), 4),
            "cutoff": cutoff,
            "value": value,
            "binder_chains": binder,
            "target_chains": target,
        }
        print(
            f"[{self.name}] {len(binder_labels)} binder x {len(target_labels)} target "
            f"residues, {len(pairs)} contacting pairs (cutoff {cutoff} A)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
