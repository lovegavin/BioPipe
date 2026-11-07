"""Minibinder interface residues from a PDB coordinate form."""
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
    residue_order,
    split_chains,
)


class MinibinderInterfaceStep(Step):
    provider = 'operon-core'
    """Report binder residues that contact a target chain set."""
    parameters_file = 'minibinder_interface.MinibinderInterfaceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'minibinder_interface',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Minibinder interface residues',
        'description': (
            'Count target residues within a heavy-atom distance cutoff of each '
            'binder residue and report the closest approach.'
        ),
        'category': 'Machine Learning',
        'icon': 'Intersect',
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
        residue_dim = ctx.step_params.get("residue_dim", "residue")
        binder_chains = split_chains(ctx.step_params.get("binder_chains", ""))
        target_chains = split_chains(ctx.step_params.get("target_chains", ""))
        cutoff = float(ctx.step_params.get("cutoff", 5.0))
        min_contacts = int(ctx.step_params.get("min_contacts", 1))
        excluded = {
            name.strip().upper()
            for name in str(ctx.step_params.get("exclude_resnames", "HOH,WAT")).split(",")
            if name.strip()
        }

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"minibinder_interface: expected a 2-D form with dims "
                f"['{atom_dim}', '{field_dim}'], got {form.dims}"
            )
        if not np.isfinite(cutoff) or cutoff <= 0:
            raise StepError("minibinder_interface: cutoff must be > 0")
        if min_contacts < 1:
            raise StepError("minibinder_interface: min_contacts must be >= 1")

        chain = decode_column(form, field_dim, "chain")
        resname = decode_column(form, field_dim, "resname")
        if chain is None or resname is None:
            raise StepError(
                "minibinder_interface: structure form lacks chain/resname columns"
            )
        keep = np.array(
            [str(name).strip().upper() not in excluded for name in resname],
            dtype=bool,
        )
        present = {str(value).strip() for value in chain[keep]}
        if not binder_chains and not target_chains:
            raise StepError(
                "minibinder_interface: set binder_chains and/or target_chains"
            )
        for name, wanted in (
            ("binder_chains", binder_chains),
            ("target_chains", target_chains),
        ):
            missing = [item for item in wanted if item not in present]
            if missing:
                raise StepError(
                    f"minibinder_interface: {name} not found in structure: "
                    f"{missing}; available chains: {sorted(present)}"
                )
        if binder_chains and target_chains and set(binder_chains) & set(target_chains):
            raise StepError(
                "minibinder_interface: binder_chains and target_chains overlap"
            )
        if not target_chains:
            target_chains = [
                item for item in sorted(present) if item not in binder_chains
            ]
        if not binder_chains:
            binder_chains = [
                item for item in sorted(present) if item not in target_chains
            ]
        if not binder_chains or not target_chains:
            raise StepError(
                "minibinder_interface: could not derive disjoint binder and target chains"
            )

        heavy = heavy_atom_mask(form, field_dim)
        chain_text = np.array([str(value).strip() for value in chain], dtype=object)
        binder_mask = keep & heavy & np.isin(chain_text, binder_chains)
        target_mask = keep & heavy & np.isin(chain_text, target_chains)
        if not binder_mask.any():
            raise StepError("minibinder_interface: binder selection has no heavy atoms")
        if not target_mask.any():
            raise StepError("minibinder_interface: target selection has no heavy atoms")

        coords = np.asarray(form.data[:, [0, 1, 2]], dtype=np.float64)
        labels = residue_labels(form, field_dim)
        target_labels = labels[target_mask]
        target_coords = coords[target_mask]

        binder_idx = np.flatnonzero(binder_mask)
        binder_order = residue_order(labels[binder_idx])
        binder_atoms = {
            residue: np.array(
                [idx for idx in binder_idx if str(labels[idx]) == residue], dtype=np.int64
            )
            for residue in binder_order
        }

        rows = []
        from scipy.spatial import cKDTree

        target_tree = cKDTree(target_coords)
        for residue in binder_order:
            atoms = binder_atoms[residue]
            counts, distances = contact_stats(coords[atoms], target_coords, cutoff)
            hits = target_tree.query_ball_point(coords[atoms], r=cutoff)
            contact_residues: dict[str, None] = {}
            for positions in hits:
                for position in positions:
                    contact_residues.setdefault(str(target_labels[position]), None)
            rows.append({
                "residue": residue,
                "contact_count": len(contact_residues),
                "min_distance": float(distances.min()) if distances.size else float("nan"),
            })

        interface = [row for row in rows if row["contact_count"] >= min_contacts]
        if not interface:
            raise StepError(
                "minibinder_interface: no binder residue has at least "
                f"{min_contacts} target contact(s) within {cutoff} A"
            )
        interface.sort(
            key=lambda row: (-row["contact_count"], row["min_distance"], row["residue"])
        )

        data = np.array(
            [[row["contact_count"], row["min_distance"]] for row in interface],
            dtype=np.float32,
        )
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {row["residue"]: i for i, row in enumerate(interface)},
                "statistic": {"contact_count": 0, "min_distance": 1},
            },
            info={
                "missing_code": np.nan,
                "binder_chains": binder_chains,
                "target_chains": target_chains,
                "cutoff": cutoff,
                "min_contacts": min_contacts,
                "n_binder_residues": len(binder_order),
                "n_interface_residues": len(interface),
                "n_target_residues": int(len(set(target_labels.tolist()))),
                "contacts": [
                    {
                        "residue": row["residue"],
                        "contact_count": row["contact_count"],
                        "min_distance": row["min_distance"],
                    }
                    for row in interface
                ],
            },
        )
        self._export_data = {
            "binder_chains": binder_chains,
            "target_chains": target_chains,
            "cutoff": cutoff,
            "min_contacts": min_contacts,
            "n_binder_residues": len(binder_order),
            "n_interface_residues": len(interface),
            "n_atom_contacts": int(sum(row["contact_count"] for row in interface)),
        }
        print(
            f"[minibinder_interface] {len(binder_order)} binder residues -> "
            f"{len(interface)} interface residues (cutoff {cutoff} A)"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
