"""Buried cavity detection on a PDB structure form.

The structure is rasterised onto a regular grid; a cell is free when the
distance from its centre to the nearest atom surface is at least the probe
radius. Free cells connected to the box boundary are solvent accessible, the
remaining free cells form buried cavities (voids) that are reported with their
volume and centroid.
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from src.core.forms.form import Form
from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, decode_column, heavy_atom_mask

_STATISTICS = ("volume", "n_cells", "centroid_x", "centroid_y", "centroid_z")
_REQUIRED = ("x", "y", "z", "element")


def _heavy(form: Form, atom_dim: str, field_dim: str) -> np.ndarray:
    fields = form.labels[field_dim]
    for name in _REQUIRED:
        if name not in fields:
            raise StepError(f"structure_cavity_scan: the structure form has no '{name}' column")
    mask = heavy_atom_mask(form, field_dim)
    if not mask.any():
        raise StepError("structure_cavity_scan: the structure form has no heavy atoms")
    return np.flatnonzero(mask)


def grid_shape(lo: np.ndarray, hi: np.ndarray, spacing: float) -> tuple[int, int, int]:
    steps = np.ceil((hi - lo) / spacing).astype(int) + 1
    return tuple(max(int(value), 1) for value in steps)


def cell_centres(lo: np.ndarray, shape: tuple[int, int, int], spacing: float) -> np.ndarray:
    axes = [lo[axis] + spacing * np.arange(shape[axis]) for axis in range(3)]
    mesh = np.meshgrid(axes[0], axes[1], axes[2], indexing="ij")
    return np.column_stack([part.ravel() for part in mesh])


def free_mask(centres: np.ndarray, shapes: np.ndarray, coords: np.ndarray, radii: np.ndarray, probe: float) -> np.ndarray:
    from scipy.spatial import cKDTree

    if coords.shape[0] == 0:
        return np.ones(centres.shape[0], dtype=bool)
    tree = cKDTree(coords)
    distance, index = tree.query(centres)
    clearance = distance - radii[index]
    return clearance >= probe


def outside_mask(free: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    reachable = np.zeros(free.shape, dtype=bool)
    queue: deque[tuple[int, int, int]] = deque()
    ix, iy, iz = shape
    for x in range(ix):
        for y in range(iy):
            for z in (0, iz - 1):
                queue.append((x, y, z))
    for y in range(iy):
        for z in range(iz):
            for x in (0, ix - 1):
                queue.append((x, y, z))
    for z in range(iz):
        for x in range(ix):
            for y in (0, iy - 1):
                queue.append((x, y, z))
    seen = np.zeros(free.shape, dtype=bool)
    while queue:
        x, y, z = queue.popleft()
        if seen[x, y, z]:
            continue
        seen[x, y, z] = True
        if not free[x, y, z]:
            continue
        reachable[x, y, z] = True
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            nx, ny, nz = x + dx, y + dy, z + dz
            if 0 <= nx < ix and 0 <= ny < iy and 0 <= nz < iz and not seen[nx, ny, nz]:
                queue.append((nx, ny, nz))
    return reachable


def cavity_components(cavity: np.ndarray, shape: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    visited = np.zeros(cavity.shape, dtype=bool)
    components: list[list[tuple[int, int, int]]] = []
    ix, iy, iz = shape
    for start in zip(*np.nonzero(cavity)):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        cells: list[tuple[int, int, int]] = []
        while stack:
            x, y, z = stack.pop()
            cells.append((x, y, z))
            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                nx, ny, nz = x + dx, y + dy, z + dz
                if 0 <= nx < ix and 0 <= ny < iy and 0 <= nz < iz and cavity[nx, ny, nz] and not visited[nx, ny, nz]:
                    visited[nx, ny, nz] = True
                    stack.append((nx, ny, nz))
        components.append(cells)
    return components


def cavity_rows(components, lo, spacing, shapes, min_volume):
    rows: list[tuple[float, ...]] = []
    for cells in components:
        volume = len(cells) * spacing ** 3
        if volume + 1e-9 < min_volume:
            continue
        indices = np.asarray(cells)
        centre = lo + spacing * indices.mean(axis=0)
        rows.append((volume, float(len(cells)), float(centre[0]), float(centre[1]), float(centre[2])))
    rows.sort(key=lambda row: (-row[0], row[2], row[3], row[4]))
    return rows


class StructureCavityScanStep(Step):
    provider = "operon-core"
    parameters_file = "structure_cavity_scan.StructureCavityScanStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_cavity_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Buried cavity scan",
        "description": "Detect buried voids on a grid and report their volume and centroid.",
        "category": "Machine Learning",
        "icon": "Cube",
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim") or "atom")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        spacing = float(ctx.step_params.get("spacing", 1.0))
        probe = float(ctx.step_params.get("probe_radius", 1.4))
        min_volume = float(ctx.step_params.get("min_volume", 20.0))
        padding = float(ctx.step_params.get("padding", 2.0))
        cavity_dim = str(ctx.step_params.get("cavity_dim") or "cavity")
        out_name = str(ctx.step_params.get("output") or "cavities")

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_cavity_scan: a PDB form with dims [{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        if not 0.5 <= spacing <= 3.0:
            raise StepError("structure_cavity_scan: spacing must be in [0.5, 3.0] angstrom")
        if not 0.5 <= probe <= 3.0:
            raise StepError("structure_cavity_scan: probe_radius must be in [0.5, 3.0] angstrom")
        if min_volume < 0:
            raise StepError("structure_cavity_scan: min_volume must not be negative")
        if padding < 0:
            raise StepError("structure_cavity_scan: padding must not be negative")

        index = _heavy(form, atom_dim, field_dim)
        coords = np.asarray(
            form.data[index][:, [column_index(form, field_dim, name) for name in ("x", "y", "z")]],
            dtype=np.float64,
        )
        from src.task.step.steps.interface_bsa import vdw_radii

        elements = decode_column(form, field_dim, "element")
        radii = np.asarray([vdw_radii([value])[0] for value in elements], dtype=np.float64)[index]

        lo = coords.min(axis=0) - padding
        hi = coords.max(axis=0) + padding
        shape = grid_shape(lo, hi, spacing)
        centres = cell_centres(lo, shape, spacing)
        free = free_mask(centres, shape, coords, radii, probe).reshape(shape)
        outside = outside_mask(free, shape)
        cavity = free & ~outside
        components = cavity_components(cavity, shape)
        rows = cavity_rows(components, lo, spacing, shape, min_volume)

        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        labels = {
            cavity_dim: {f"cavity{position + 1}": position for position in range(len(rows))},
            "statistic": {name: position for position, name in enumerate(_STATISTICS)},
        }
        out = Form(data=data, dims=[cavity_dim, "statistic"], labels=labels, info={
            "spacing": spacing,
            "probe_radius": probe,
            "min_volume": min_volume,
            "padding": padding,
            "n_cavities": len(rows),
            "total_volume": float(sum(row[0] for row in rows)),
            "unit": "A^3",
            "missing_code": np.nan,
        })
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_cavities": len(rows),
            "total_volume": float(sum(row[0] for row in rows)),
            "spacing": spacing,
            "probe_radius": probe,
        }
        print(f"[structure_cavity_scan] {len(rows)} cavities, total {self._export_data['total_volume']:.1f} A^3")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
