"""Contact-density interface hotspots for two chain groups."""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._protein_common import decode_column, has_column, heavy_atom_mask, residue_labels
from ._structure_common import atom_coords, pick_chain_sides
from .interface_bsa import sasa_per_atom, vdw_radii


def contact_statistics(
    query: np.ndarray,
    reference: np.ndarray,
    cutoff: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Number of reference points within cutoff and the nearest distance."""

    if not len(query) or not len(reference):
        return np.zeros(len(query), dtype=np.int64), np.full(len(query), np.inf)
    tree = cKDTree(reference)
    counts = np.asarray(
        tree.query_ball_point(query, r=cutoff, return_length=True), dtype=np.int64
    )
    distances = np.asarray(tree.query(query)[0], dtype=np.float64)
    return counts, distances


class InterfaceHotspotsStep(Step):
    """Rank interface residues by contact density and buried area."""

    provider = 'operon-core'
    parameters_file = 'interface_hotspots.InterfaceHotspotsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'interface_hotspots',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Interface hotspots',
        'description': (
            'Rank the residues of a binder-target interface by the number of '
            'cross-chain heavy-atom contacts, the closest contact distance and '
            'the solvent-accessible area they bury on complex formation.'
        ),
        'category': 'Machine Learning',
        'icon': 'ChartScatter',
        'contracts': {
            'version': 1,
            'inputs': [
                {
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
        cutoff = float(params.get("cutoff", 5.0))
        min_contacts = int(params.get("min_contacts", 1))
        probe_radius = float(params.get("probe_radius", 1.4))
        n_points = int(params.get("n_points", 92))
        sort_by = str(params.get("sort_by", "contacts")).strip().lower()
        excluded = {
            token.strip().upper()
            for token in str(params.get("exclude_resnames", "HOH,WAT")).split(",")
            if token.strip()
        }
        out_name = params.get("output", self.name)

        if cutoff <= 0.0:
            raise StepError("interface_hotspots: cutoff must be positive")
        if min_contacts < 1:
            raise StepError("interface_hotspots: min_contacts must be at least one")
        if not 1.0 <= probe_radius <= 3.0:
            raise StepError("interface_hotspots: probe_radius must be between 1.0 and 3.0")
        if not 64 <= n_points <= 1024:
            raise StepError("interface_hotspots: n_points must be between 64 and 1024")
        if sort_by not in ("contacts", "buried"):
            raise StepError("interface_hotspots: sort_by must be 'contacts' or 'buried'")

        form = inputs[0]
        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"interface_hotspots: expected a [{atom_dim}, {field_dim}] PDB form, "
                f"got {list(form.dims)}"
            )
        for column in ("x", "y", "z", "chain", "resname", "residue_number", "element"):
            if not has_column(form, field_dim, column):
                raise StepError(f"interface_hotspots: the PDB form has no '{column}' column")

        chain = np.asarray([str(value).strip() for value in decode_column(form, field_dim, "chain")])
        resname = np.asarray(
            [str(value).strip().upper() for value in decode_column(form, field_dim, "resname")]
        )
        keep = heavy_atom_mask(form, field_dim)
        if excluded:
            keep = keep & ~np.isin(resname, list(excluded))
        if not keep.any():
            raise StepError("interface_hotspots: no heavy atoms left after exclusions")

        binder, target = pick_chain_sides(
            set(chain[keep].tolist()),
            params.get("binder_chains", ""),
            params.get("target_chains", ""),
            "interface_hotspots",
        )

        coords = atom_coords(form, field_dim)
        residue = np.asarray(residue_labels(form, field_dim), dtype=object)
        binder_mask = keep & np.isin(chain, binder)
        target_mask = keep & np.isin(chain, target)
        selected = binder_mask | target_mask

        counts = np.zeros(len(form.data), dtype=np.int64)
        nearest = np.full(len(form.data), np.inf)
        binder_rows = np.flatnonzero(binder_mask)
        if len(binder_rows):
            counts[binder_rows], nearest[binder_rows] = contact_statistics(
                coords[binder_rows], coords[target_mask], cutoff
            )
        target_rows = np.flatnonzero(target_mask)
        if len(target_rows):
            counts[target_rows], nearest[target_rows] = contact_statistics(
                coords[target_rows], coords[binder_mask], cutoff
            )

        radii = vdw_radii(decode_column(form, field_dim, "element"))
        complex_sasa = np.zeros(len(form.data), dtype=np.float64)
        complex_sasa[selected] = sasa_per_atom(
            coords[selected], radii[selected], probe_radius=probe_radius, n_points=n_points
        )
        free_sasa = np.zeros(len(form.data), dtype=np.float64)
        for mask in (binder_mask, target_mask):
            free_sasa[mask] = sasa_per_atom(
                coords[mask], radii[mask], probe_radius=probe_radius, n_points=n_points
            )
        buried = np.clip(free_sasa - complex_sasa, 0.0, None)

        labels = residue[selected]
        unique: list[str] = []
        totals: dict[str, dict[str, float]] = {}
        for label, count, distance, area in zip(
            labels.tolist(),
            counts[selected].tolist(),
            nearest[selected].tolist(),
            buried[selected].tolist(),
        ):
            if label not in totals:
                unique.append(label)
                totals[label] = {"contacts": 0.0, "distance": np.inf, "buried": 0.0}
            totals[label]["contacts"] += float(count)
            totals[label]["distance"] = min(totals[label]["distance"], float(distance))
            totals[label]["buried"] += float(area)

        rows = [
            label
            for label in unique
            if totals[label]["contacts"] >= min_contacts and np.isfinite(totals[label]["distance"])
        ]
        if sort_by == "buried":
            rows.sort(key=lambda label: (-totals[label]["buried"], label))
        else:
            rows.sort(
                key=lambda label: (
                    -totals[label]["contacts"],
                    -totals[label]["buried"],
                    label,
                )
            )

        if rows:
            data = np.asarray(
                [
                    [
                        totals[label]["contacts"],
                        totals[label]["distance"],
                        totals[label]["buried"],
                    ]
                    for label in rows
                ],
                dtype=np.float32,
            )
        else:
            data = np.zeros((0, 3), dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: position for position, label in enumerate(rows)},
                "statistic": {
                    "contact_count": 0,
                    "min_distance": 1,
                    "buried_area": 2,
                },
            },
            info={
                "binder_chains": binder,
                "target_chains": target,
                "cutoff": cutoff,
                "min_contacts": min_contacts,
                "probe_radius": probe_radius,
                "n_points": n_points,
                "sort_by": sort_by,
                "total_buried_area": float(
                    buried[binder_mask].sum() + buried[target_mask].sum()
                ),
                "hotspots": len(rows),
                "unit": "A^2",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "binder_chains": binder,
            "target_chains": target,
            "hotspots": len(rows),
            "cutoff": cutoff,
            "total_buried_area": round(
                float(buried[binder_mask].sum() + buried[target_mask].sum()), 4
            ),
        }
        print(
            f"[{self.name}] interface {'+'.join(binder)} / {'+'.join(target)}: "
            f"{len(rows)} hotspots at {cutoff:.1f} A"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
