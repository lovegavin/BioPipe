"""Buried solvent-accessible surface area at a protein chain interface."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import (
    column_index,
    decode_column,
    has_column,
    heavy_atom_mask,
    residue_labels,
    split_chains,
)

# Bondi van der Waals radii in angstrom; unknown elements fall back to 1.70.
_VDW_RADII = {
    "H": 1.20,
    "D": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "F": 1.47,
    "P": 1.80,
    "S": 1.80,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
    "B": 1.92,
    "SI": 2.10,
    "SE": 1.90,
}
_DEFAULT_RADIUS = 1.70


def sphere_points(n_points: int) -> np.ndarray:
    """Deterministic, evenly spread points on the unit sphere."""
    indices = np.arange(n_points, dtype=np.float64) + 0.5
    phi = np.arccos(1.0 - 2.0 * indices / n_points)
    theta = np.pi * (1.0 + 5.0 ** 0.5) * indices
    return np.stack(
        [
            np.cos(theta) * np.sin(phi),
            np.sin(theta) * np.sin(phi),
            np.cos(phi),
        ],
        axis=1,
    )


def vdw_radii(elements) -> np.ndarray:
    return np.array(
        [
            _VDW_RADII.get(str(element).strip().upper(), _DEFAULT_RADIUS)
            for element in elements
        ],
        dtype=np.float64,
    )


def sasa_per_atom(
    coords: np.ndarray,
    radii: np.ndarray,
    *,
    probe_radius: float = 1.4,
    n_points: int = 92,
) -> np.ndarray:
    """Shrake-Rupley solvent accessible surface area of every atom."""
    from scipy.spatial import cKDTree

    count = coords.shape[0]
    if count == 0:
        return np.zeros(0, dtype=np.float64)
    expanded = radii + probe_radius
    unit = sphere_points(n_points)
    tree = cKDTree(coords)
    max_radius = float(radii.max())
    areas = np.zeros(count, dtype=np.float64)
    reach = 2.0 * (max_radius + probe_radius) + 1e-6
    for index in range(count):
        neighbors = tree.query_ball_point(coords[index], reach)
        free = np.ones(n_points, dtype=bool)
        for other in neighbors:
            if other == index:
                continue
            points = coords[index] + expanded[index] * unit
            distance = np.linalg.norm(points - coords[other], axis=1)
            free &= distance >= expanded[other]
            if not free.any():
                break
        areas[index] = 4.0 * np.pi * expanded[index] ** 2 * free.mean()
    return areas


def _pick_sides(
    present: set[str], binder_text: str, target_text: str
) -> tuple[list[str], list[str]]:
    """Select binder and target chains, deriving the empty side when possible."""
    from src.task.step.steps._structure_common import pick_chain_sides

    return pick_chain_sides(present, binder_text, target_text, "interface_bsa")


class InterfaceBsaStep(Step):
    """Buried surface area and interface residues for two chain groups."""

    provider = 'operon-core'
    parameters_file = 'interface_bsa.InterfaceBsaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'interface_bsa',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Interface buried area',
        'description': (
            'Compute the solvent accessible surface area of two chain groups '
            'alone and in complex with a Shrake-Rupley algorithm, report the '
            'buried area of every interface residue, and rank the contact '
            'hot spots of a binder-target complex.'
        ),
        'category': 'Machine Learning',
        'icon': 'Intersect',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'info': {
                        'encoders': {'type': 'object', 'optional': True},
                    },
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
        'dependency_imports': ['scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        residue_dim = str(params.get("residue_dim", "residue")).strip() or "residue"
        probe_radius = float(params.get("probe_radius", 1.4))
        n_points = int(params.get("n_points", 92))
        min_buried = float(params.get("min_buried", 0.0))
        excluded = {
            token.strip().upper()
            for token in str(params.get("exclude_resnames", "HOH,WAT")).split(",")
            if token.strip()
        }
        out_name = params.get("output", self.name)

        if not 1.0 <= probe_radius <= 3.0:
            raise StepError("interface_bsa: probe_radius must be between 1.0 and 3.0")
        if not 64 <= n_points <= 1024:
            raise StepError("interface_bsa: n_points must be between 64 and 1024")
        if min_buried < 0.0:
            raise StepError("interface_bsa: min_buried must be zero or positive")

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"interface_bsa: expected a [{atom_dim}, {field_dim}] PDB form, "
                f"got {list(form.dims)}"
            )
        for column in ("x", "y", "z", "chain", "resname", "element"):
            if not has_column(form, field_dim, column):
                raise StepError(
                    f"interface_bsa: the PDB form has no '{column}' column"
                )

        chain = np.array([str(value).strip() for value in decode_column(form, field_dim, "chain")])
        resname = np.array([str(value).strip().upper() for value in decode_column(form, field_dim, "resname")])
        keep = heavy_atom_mask(form, field_dim)
        if excluded:
            keep = keep & ~np.isin(resname, list(excluded))
        if not keep.any():
            raise StepError("interface_bsa: no heavy atoms left after exclusions")

        binder, target = _pick_sides(
            set(chain[keep].tolist()),
            params.get("binder_chains", ""),
            params.get("target_chains", ""),
        )
        counterpart = set(binder) | set(target)

        coords = np.column_stack(
            [
                np.asarray(
                    form.data[:, column_index(form, field_dim, column)],
                    dtype=np.float64,
                )
                for column in ("x", "y", "z")
            ]
        )
        residue = np.asarray(residue_labels(form, field_dim), dtype=object)
        radii = vdw_radii(decode_column(form, field_dim, "element"))
        selected = keep & np.isin(chain, list(counterpart))

        complex_sasa = np.zeros(len(form.data), dtype=np.float64)
        complex_sasa[selected] = sasa_per_atom(
            coords[selected],
            radii[selected],
            probe_radius=probe_radius,
            n_points=n_points,
        )
        binder_mask = selected & np.isin(chain, binder)
        target_mask = selected & np.isin(chain, target)
        binder_free = np.zeros(len(form.data), dtype=np.float64)
        binder_free[binder_mask] = sasa_per_atom(
            coords[binder_mask],
            radii[binder_mask],
            probe_radius=probe_radius,
            n_points=n_points,
        )
        target_free = np.zeros(len(form.data), dtype=np.float64)
        target_free[target_mask] = sasa_per_atom(
            coords[target_mask],
            radii[target_mask],
            probe_radius=probe_radius,
            n_points=n_points,
        )
        free_sasa = binder_free + target_free
        buried_atom = np.clip(free_sasa - complex_sasa, 0.0, None)

        labels = residue[selected]
        unique: list[str] = []
        totals: dict[str, float] = {}
        exposed: dict[str, float] = {}
        for label, buried, accessible in zip(
            labels.tolist(), buried_atom[selected].tolist(), complex_sasa[selected].tolist()
        ):
            if label not in totals:
                unique.append(label)
                totals[label] = 0.0
                exposed[label] = 0.0
            totals[label] += buried
            exposed[label] += accessible

        binder_buried = float(buried_atom[binder_mask].sum())
        target_buried = float(buried_atom[target_mask].sum())
        rows = [
            label for label in unique if totals[label] > min_buried + 1e-12
        ]
        rows.sort(key=lambda label: (-totals[label], label))

        if rows:
            data = np.array(
                [[totals[label], exposed[label]] for label in rows],
                dtype=np.float32,
            )
        else:
            data = np.zeros((0, 2), dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: position for position, label in enumerate(rows)},
                "statistic": {"buried_area": 0, "complex_area": 1},
            },
            info={
                "total_buried_area": binder_buried + target_buried,
                "binder_buried_area": binder_buried,
                "target_buried_area": target_buried,
                "binder_chains": binder,
                "target_chains": target,
                "probe_radius": probe_radius,
                "n_points": n_points,
                "interface_residues": len(rows),
                "unit": "A^2",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "binder_chains": binder,
            "target_chains": target,
            "interface_residues": len(rows),
            "total_buried_area": round(binder_buried + target_buried, 4),
            "probe_radius": probe_radius,
            "n_points": n_points,
        }
        print(
            f"[{self.name}] interface {'+'.join(binder)} / {'+'.join(target)}: "
            f"{len(rows)} residues, {binder_buried + target_buried:.1f} A^2 buried"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
