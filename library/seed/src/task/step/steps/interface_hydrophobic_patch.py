"""Group hydrophobic binder residues that contact a target into surface patches."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import (
    column_index,
    contact_stats,
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
    split_chains,
)
from ._structure_common import pick_chain_sides

_STATISTICS = ("n_residues", "n_hydrophobic", "hydrophobic_fraction", "n_contacts", "mean_contacts")
_DEFAULT_HYDROPHOBIC = "ALA,VAL,ILE,LEU,MET,PHE,TRP,TYR,CYS"


def _residue_groups(labels: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Return ``(label, atom_index_array)`` groups in first-appearance order."""
    groups: dict[str, list[int]] = {}
    for index, label in enumerate(labels):
        groups.setdefault(str(label), []).append(index)
    return [(label, np.asarray(indices, dtype=np.int64)) for label, indices in groups.items()]


def _ca_positions(
    form: Form, field_dim: str, labels: np.ndarray, groups, coords: np.ndarray
) -> np.ndarray:
    """Return one anchor position per residue (CA if present, else the atom mean)."""
    if has_column(form, field_dim, "atom_name"):
        names = decode_column(form, field_dim, "atom_name")
        if names is not None:
            names = np.asarray([str(name).strip() for name in names])
            anchors = []
            for _, indices in groups:
                ca = indices[names[indices] == "CA"]
                anchors.append(coords[ca[0]] if len(ca) else coords[indices].mean(axis=0))
            return np.asarray(anchors, dtype=np.float64)
    return np.asarray([coords[indices].mean(axis=0) for _, indices in groups], dtype=np.float64)


def cluster_residues(anchors: np.ndarray, cutoff: float) -> list[list[int]]:
    """Single-linkage clusters of anchor positions within ``cutoff``."""
    parent = list(range(len(anchors)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left in range(len(anchors)):
        for right in range(left + 1, len(anchors)):
            if float(np.linalg.norm(anchors[left] - anchors[right])) <= cutoff:
                union(left, right)
    clusters: dict[int, list[int]] = {}
    for index in range(len(anchors)):
        clusters.setdefault(find(index), []).append(index)
    return sorted(clusters.values(), key=lambda members: (-len(members), members[0]))


class InterfaceHydrophobicPatchStep(Step):
    """Group hydrophobic binder residues that contact a target into surface patches."""

    provider = "operon-core"
    parameters_file = "interface_hydrophobic_patch.InterfaceHydrophobicPatchStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "interface_hydrophobic_patch",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface Hydrophobic Patches",
        "description": (
            "Cluster the binder residues that contact a target chain set into patches and "
            "report each patch's size, hydrophobic content and contact count."
        ),
        "category": "Machine Learning",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "atom_dim", "default": "atom"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
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
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        atom_dim = str(ctx.step_params.get("atom_dim", "atom"))
        field_dim = str(ctx.step_params.get("field_dim", "field"))
        patch_dim = str(ctx.step_params.get("patch_dim", "patch"))
        binder_text = str(ctx.step_params.get("binder_chains", "A"))
        target_text = str(ctx.step_params.get("target_chains", ""))
        cutoff = float(ctx.step_params.get("cutoff", 4.5))
        ca_cutoff = float(ctx.step_params.get("ca_cutoff", 10.0))
        min_residues = int(ctx.step_params.get("min_residues", 1))
        hydrophobic_text = str(ctx.step_params.get("hydrophobic_resnames", _DEFAULT_HYDROPHOBIC))
        exclude_text = str(ctx.step_params.get("exclude_resnames", "HOH,WAT"))
        output_name = str(ctx.step_params.get("output", "patches"))
        if not 0 < cutoff <= 10.0:
            raise StepError("cutoff must be in (0, 10] angstrom")
        if not 0 < ca_cutoff <= 30.0:
            raise StepError("ca_cutoff must be in (0, 30] angstrom")
        if min_residues < 1:
            raise StepError("min_residues must be at least 1")
        hydrophobic = {name.upper() for name in split_chains(hydrophobic_text)}
        if not hydrophobic:
            raise StepError("hydrophobic_resnames must name at least one residue")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(f"a PDB form with dims [{atom_dim}, {field_dim}] is required")
        labels = residue_labels(form, field_dim)
        chains = decode_column(form, field_dim, "chain")
        if chains is None:
            raise StepError("the structure form has no 'chain' column")
        chains = np.asarray([str(value).strip() or "_" for value in chains])
        resnames = decode_column(form, field_dim, "resname")
        if resnames is None:
            raise StepError("the structure form has no 'resname' column")
        resnames = np.asarray([str(value).strip().upper() or "UNK" for value in resnames])
        coords = np.column_stack(
            [
                np.asarray(form.data[:, column_index(form, field_dim, axis)], dtype=np.float64)
                for axis in ("x", "y", "z")
            ]
        )
        keep = heavy_atom_mask(form, field_dim)
        if exclude_text.strip():
            excluded = {name.upper() for name in split_chains(exclude_text)}
            keep &= ~np.isin(resnames, list(excluded))
        if not np.any(keep):
            raise StepError("the structure form has no heavy atoms to analyse")
        binder, target = pick_chain_sides(
            set(chains[keep]), binder_text, target_text, "interface_hydrophobic_patch"
        )
        groups = _residue_groups(labels)
        binder_residues = [entry for entry in groups if entry[0].split(":")[0] in binder]
        target_atoms = np.concatenate(
            [indices for label, indices in groups if label.split(":")[0] in target and np.all(keep[indices])]
            or [np.zeros(0, dtype=np.int64)]
        )
        if len(target_atoms) == 0:
            raise StepError("the target chains have no heavy atoms in the structure form")
        target_coords = coords[target_atoms]
        binder_coords = [coords[indices[keep[indices]]] for _, indices in binder_residues]
        interface: list[int] = []
        counts: list[int] = []
        for offset, residue_coords in enumerate(binder_coords):
            if len(residue_coords) == 0:
                continue
            residue_counts, distances = contact_stats(residue_coords, target_coords, cutoff)
            if float(np.min(distances)) <= cutoff:
                interface.append(offset)
                counts.append(int(np.sum(residue_counts)))
        anchors = _ca_positions(
            form, field_dim, labels, [binder_residues[index] for index in interface], coords
        )
        members = cluster_residues(anchors, ca_cutoff) if interface else []
        patches = [cluster for cluster in members if len(cluster) >= min_residues]
        rows: list[list[float]] = []
        patch_details: list[dict] = []
        for cluster in patches:
            selected = [interface[index] for index in cluster]
            labels_in_patch = [binder_residues[index][0] for index in selected]
            hydrophobic_count = sum(
                1 for index in selected if str(resnames[binder_residues[index][1][0]]).upper() in hydrophobic
            )
            contact_total = sum(counts[index] for index in cluster)
            residues = len(selected)
            rows.append(
                [
                    float(residues),
                    float(hydrophobic_count),
                    hydrophobic_count / residues,
                    float(contact_total),
                    contact_total / residues,
                ]
            )
            patch_details.append(
                {
                    "residues": labels_in_patch,
                    "hydrophobic": hydrophobic_count,
                    "contacts": contact_total,
                }
            )
        values = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        output = Form(
            data=values,
            dims=[patch_dim, "statistic"],
            labels={
                patch_dim: {f"patch{index + 1}": index for index in range(len(rows))},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "patches": patch_details,
                "binder_chains": sorted(binder),
                "target_chains": sorted(target),
                "cutoff": cutoff,
                "ca_cutoff": ca_cutoff,
                "hydrophobic_resnames": sorted(hydrophobic),
                "interface_residues": len(interface),
                "n_patches": len(rows),
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_patches": len(rows),
            "interface_residues": len(interface),
            "hydrophobic_interface_residues": int(output.data[:, 1].sum()) if rows else 0,
            "binder_chains": sorted(binder),
            "target_chains": sorted(target),
        }
        print(
            f"[interface_hydrophobic_patch] {len(interface)} interface binder residues in "
            f"{len(rows)} patches"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
