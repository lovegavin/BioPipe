"""Residue contact network built from a heavy-atom PDB form."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import decode_column, heavy_atom_mask, residue_labels
from ._structure_common import atom_coords, field_columns


def residue_graph(
    coords: np.ndarray,
    residue_index: np.ndarray,
    residue_chains: np.ndarray,
    cutoff: float,
    include_intra: bool,
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, float]]]:
    """Return (contact counts, nearest distance, contact pairs) per residue."""

    count = int(residue_chains.shape[0])
    counts = np.zeros(count, dtype=np.int64)
    nearest = np.full(count, np.nan, dtype=np.float64)
    if len(coords) < 2:
        return counts, nearest, []

    tree = cKDTree(coords)
    pair_array = tree.query_pairs(r=cutoff, output_type="ndarray")
    best: dict[tuple[int, int], float] = {}
    for left, right in pair_array:
        first = int(residue_index[left])
        second = int(residue_index[right])
        if first == second:
            continue
        if not include_intra and residue_chains[first] == residue_chains[second]:
            continue
        distance = float(np.linalg.norm(coords[left] - coords[right]))
        key = (first, second) if first < second else (second, first)
        previous = best.get(key)
        if previous is None or distance < previous:
            best[key] = distance

    partners: list[set[int]] = [set() for _ in range(count)]
    for (first, second), distance in best.items():
        partners[first].add(second)
        partners[second].add(first)
        for index in (first, second):
            if np.isnan(nearest[index]) or distance < nearest[index]:
                nearest[index] = distance
    for index, values in enumerate(partners):
        counts[index] = len(values)

    pairs = sorted(
        [
            (first, second, round(distance, 4))
            for (first, second), distance in best.items()
        ]
    )
    return counts, nearest, pairs


class StructureContactsStep(Step):
    """Residue-level contact counts and nearest partner distances."""

    provider = 'operon-core'
    parameters_file = 'structure_contacts.StructureContactsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'structure_contacts',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Residue contact network',
        'description': (
            'Convert a heavy-atom PDB form into a residue contact graph: for '
            'every residue report how many partner residues lie within the '
            'cutoff (cross-chain by default) and the distance to the nearest '
            'partner.'
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
        'dependencies': ['numpy>=1.24', 'scipy>=1.10'],
        'dependency_imports': ['numpy', 'scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        residue_dim = str(params.get("residue_dim", "residue")).strip() or "residue"
        cutoff = float(params.get("cutoff", 4.5))
        include_intra = bool(params.get("include_intra", False))
        min_contacts = int(params.get("min_contacts", 1))
        excluded = {
            value.strip().upper()
            for value in str(params.get("exclude_resnames", "HOH,WAT")).split(",")
            if value.strip()
        }
        out_name = params.get("output", self.name)

        if not 0.0 < cutoff <= 10.0:
            raise StepError("structure_contacts: cutoff must be in (0, 10] angstrom")
        if min_contacts < 0:
            raise StepError("structure_contacts: min_contacts must not be negative")

        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_contacts: a PDB form with dims [{atom_dim}, {field_dim}] is "
                f"required, got {list(form.dims)}"
            )
        field_columns(form, field_dim, ("x", "y", "z"))
        if form.data.shape[0] == 0:
            raise StepError("structure_contacts: the PDB form has no atoms")

        heavy = heavy_atom_mask(form, field_dim)
        resnames = np.asarray(
            [str(value).strip().upper() for value in decode_column(form, field_dim, "resname")],
            dtype=object,
        )
        if excluded:
            heavy = heavy & ~np.isin(resnames, sorted(excluded))
        if not heavy.any():
            raise StepError("structure_contacts: the PDB form has no heavy atoms to analyse")

        labels = [str(value) for value in residue_labels(form, field_dim)]
        ordered: list[str] = []
        seen: dict[str, int] = {}
        residue_index = np.empty(len(labels), dtype=np.int64)
        for index, label in enumerate(labels):
            position = seen.get(label)
            if position is None:
                position = len(ordered)
                seen[label] = position
                ordered.append(label)
            residue_index[index] = position

        chains = [str(value).strip() for value in decode_column(form, field_dim, "chain")]
        residue_chains = np.empty(len(ordered), dtype=object)
        for index, chain in enumerate(chains):
            residue_chains[residue_index[index]] = chain

        if len(ordered) < 2:
            raise StepError(
                "structure_contacts: at least two residues are required, "
                f"found {len(ordered)}"
            )

        coords = atom_coords(form, field_dim)[heavy]
        index = residue_index[heavy]
        counts, nearest, pairs = residue_graph(coords, index, residue_chains, cutoff, include_intra)

        keep = [position for position in range(len(ordered)) if counts[position] >= min_contacts]
        if not keep:
            label_list: list[str] = []
            data = np.zeros((0, 2), dtype=np.float32)
        else:
            rows = sorted(
                keep,
                key=lambda position: (
                    -int(counts[position]),
                    float(nearest[position]) if np.isfinite(nearest[position]) else np.inf,
                    ordered[position],
                ),
            )
            label_list = [ordered[position] for position in rows]
            data = np.asarray(
                [[float(counts[position]), float(nearest[position])] for position in rows],
                dtype=np.float32,
            )

        form_out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: position for position, label in enumerate(label_list)},
                "statistic": {"contact_count": 0, "min_distance": 1},
            },
            info={
                "missing_code": np.nan,
                "cutoff": cutoff,
                "include_intra": include_intra,
                "chains": sorted({str(value) for value in residue_chains}),
                "excluded_resnames": sorted(excluded),
                "n_residues": len(ordered),
                "n_contact_residues": int((counts > 0).sum()),
                "n_pairs": len(pairs),
                "residue_pairs": [[ordered[first], ordered[second], distance] for first, second, distance in pairs],
                "unit": "A",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_residues": len(ordered),
            "n_contact_residues": int((counts > 0).sum()),
            "n_rows": len(label_list),
            "n_pairs": len(pairs),
            "cutoff": cutoff,
            "include_intra": include_intra,
            "chains": sorted({str(value) for value in residue_chains}),
        }
        print(
            f"[{self.name}] {len(pairs)} residue contacts over {len(ordered)} residues "
            f"({int((counts > 0).sum())} contacting, cutoff {cutoff:.1f} A)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
