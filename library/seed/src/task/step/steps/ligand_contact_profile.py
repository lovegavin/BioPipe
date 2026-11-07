"""Ligand contact profile from a PDB coordinate form."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._protein_common import (
    contact_stats,
    decode_column,
    heavy_atom_mask,
    residue_labels,
    split_chains,
)


class LigandContactProfileStep(Step):
    provider = 'operon-core'
    """Profile per-atom ligand contacts against the surrounding structure."""
    parameters_file = 'ligand_contact_profile.LigandContactProfileStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ligand_contact_profile',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Ligand contact profile',
        'description': (
            'For every ligand atom report how many distinct receptor residues '
            'lie within a heavy-atom cutoff and the nearest contact residue.'
        ),
        'category': 'Machine Learning',
        'icon': 'Columns',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {'encoders': {'type': 'object', 'optional': True}},
                'dims': [
                    {'param': 'atom_dim', 'default': 'atom'},
                    {'param': 'field_dim', 'default': 'field'},
                ],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
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
        form = inputs[0]
        atom_dim = ctx.step_params.get("atom_dim", "atom")
        field_dim = ctx.step_params.get("field_dim", "field")
        ligand_resname = str(ctx.step_params.get("ligand_resname", "")).strip()
        ligand_chains = split_chains(ctx.step_params.get("ligand_chains", ""))
        cutoff = float(ctx.step_params.get("cutoff", 4.5))
        excluded = {
            name.strip().upper()
            for name in str(ctx.step_params.get("exclude_resnames", "HOH,WAT")).split(",")
            if name.strip()
        }

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"ligand_contact_profile: expected a 2-D form with dims "
                f"['{atom_dim}', '{field_dim}'], got {form.dims}"
            )
        if not ligand_resname:
            raise StepError("ligand_contact_profile: ligand_resname is required")
        if not np.isfinite(cutoff) or cutoff <= 0:
            raise StepError("ligand_contact_profile: cutoff must be > 0")

        chain = decode_column(form, field_dim, "chain")
        resname = decode_column(form, field_dim, "resname")
        if chain is None or resname is None:
            raise StepError(
                "ligand_contact_profile: structure form lacks chain/resname columns"
            )
        ligand_name = ligand_resname.upper()
        chain_text = np.array([str(value).strip() for value in chain], dtype=object)
        resname_text = np.array(
            [str(value).strip().upper() for value in resname], dtype=object
        )
        heavy = heavy_atom_mask(form, field_dim)

        ligand_mask = heavy & (resname_text == ligand_name)
        if ligand_chains:
            ligand_mask = ligand_mask & np.isin(chain_text, ligand_chains)
        if not ligand_mask.any():
            available = sorted(set(resname_text.tolist()))
            raise StepError(
                f"ligand_contact_profile: no ligand atoms named "
                f"'{ligand_resname}'; available residue names: {available[:40]}"
            )

        receptor_mask = (
            heavy
            & ~ligand_mask
            & ~np.isin(resname_text, sorted(excluded))
        )
        if not receptor_mask.any():
            raise StepError(
                "ligand_contact_profile: no receptor atoms remain after filtering"
            )

        coords = np.asarray(form.data[:, [0, 1, 2]], dtype=np.float64)
        labels = residue_labels(form, field_dim)
        receptor_labels = labels[receptor_mask]
        ligand_indices = np.flatnonzero(ligand_mask)

        from scipy.spatial import cKDTree

        receptor_tree = cKDTree(coords[receptor_mask])
        hits = receptor_tree.query_ball_point(coords[ligand_indices], r=cutoff)
        distances, nearest = receptor_tree.query(coords[ligand_indices], k=1)

        atom_labels = self._atom_labels(form, atom_dim)
        rows = []
        for position, atom_index in enumerate(ligand_indices):
            contact_residues: dict[str, None] = {}
            for receptor_position in hits[position]:
                contact_residues.setdefault(
                    str(receptor_labels[receptor_position]), None
                )
            nearest_label = (
                str(receptor_labels[nearest[position]])
                if int(nearest[position]) < len(receptor_labels)
                else ""
            )
            rows.append({
                "label": atom_labels[atom_index],
                "contact_count": len(contact_residues),
                "min_distance": float(distances[position]),
                "nearest_residue": nearest_label,
                "contact_residues": list(contact_residues),
            })

        data = np.array(
            [[row["contact_count"], row["min_distance"]] for row in rows],
            dtype=np.float32,
        )
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=data,
            dims=[atom_dim, "statistic"],
            labels={
                atom_dim: {row["label"]: i for i, row in enumerate(rows)},
                "statistic": {"contact_count": 0, "min_distance": 1},
            },
            info={
                "missing_code": np.nan,
                "ligand_resname": ligand_name,
                "ligand_chains": ligand_chains,
                "cutoff": cutoff,
                "n_ligand_atoms": len(rows),
                "n_receptor_residues": int(len(set(receptor_labels.tolist()))),
                "nearest_residue": [row["nearest_residue"] for row in rows],
                "contact_residues": [row["contact_residues"] for row in rows],
            },
        )
        self._export_data = {
            "ligand_resname": ligand_name,
            "ligand_chains": ligand_chains,
            "cutoff": cutoff,
            "n_ligand_atoms": len(rows),
            "n_contacted_residues": int(
                len({residue for row in rows for residue in row["contact_residues"]})
            ),
            "min_distance": float(min(row["min_distance"] for row in rows)),
            "nearest_residue": rows[0]["nearest_residue"] if rows else "",
        }
        print(
            f"[ligand_contact_profile] {len(rows)} {ligand_name} atoms, "
            f"{self._export_data['n_contacted_residues']} contacted residues "
            f"(cutoff {cutoff} A)"
        )

    @staticmethod
    def _atom_labels(form: Form, atom_dim: str) -> list[str]:
        labels = form.labels.get(atom_dim) or {}
        ordered = ["" for _ in range(len(labels))]
        for label, position in labels.items():
            ordered[int(position)] = str(label)
        return ordered

    def export(self, ctx: Context) -> dict:
        return self._export_data
