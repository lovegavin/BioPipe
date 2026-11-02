"""Interface core residues from per-residue buried surface area."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, has_column
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.interface_bsa import sasa_per_atom, vdw_radii


def _column(form: Form, field_dim: str, name: str) -> np.ndarray:
    return np.asarray(form.data[:, column_index(form, field_dim, name)], dtype=np.float64)


def _residue_labels(form: Form, field_dim: str) -> list[str]:
    chains = _column(form, field_dim, "chain")
    resnames = _column(form, field_dim, "resname")
    numbers = _column(form, field_dim, "residue_number")
    labels = []
    for chain, resname, number in zip(chains, resnames, numbers):
        labels.append(f"{_decode(form, field_dim, 'chain', chain)}:{_decode(form, field_dim, 'resname', resname)}:{int(number)}")
    return labels


def _decode(form: Form, field_dim: str, name: str, value: float) -> str:
    encoder = (form.info.get("encoders") or {}).get(field_dim, {}).get(name)
    if encoder is not None:
        return str(encoder.inverse_transform([int(value)])[0])
    return str(value)


def relative_sasa(
    coordinates: np.ndarray,
    radii: np.ndarray,
    side_masks: list[np.ndarray],
    *,
    probe_radius: float = 1.4,
    n_points: int = 92,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Complex SASA and the SASA of every side in isolation."""

    complex_sasa = sasa_per_atom(coordinates, radii, probe_radius=probe_radius, n_points=n_points)
    isolated = []
    for mask in side_masks:
        if not mask.any():
            isolated.append(np.zeros(coordinates.shape[0], dtype=np.float64))
            continue
        values = sasa_per_atom(
            coordinates[mask], radii[mask], probe_radius=probe_radius, n_points=n_points
        )
        full = np.zeros(coordinates.shape[0], dtype=np.float64)
        full[mask] = values
        isolated.append(full)
    return complex_sasa, isolated


def core_rows(
    labels: list[str],
    chains: list[str],
    delta: np.ndarray,
    isolated_sum: np.ndarray,
    side_of_atom: np.ndarray,
    *,
    core_fraction: float = 0.5,
    min_delta: float = 0.01,
) -> list[dict]:
    """Aggregate per-atom burial into per-residue interface core rows."""

    order: dict[tuple[str, str], int] = {}
    for label, chain in zip(labels, chains):
        order.setdefault((label, chain), len(order))
    totals = {key: 0.0 for key in order}
    isolated = {key: 0.0 for key in order}
    for label, chain, value, isolated_value in zip(labels, chains, delta, isolated_sum):
        key = (label, chain)
        totals[key] += float(value)
        isolated[key] += float(isolated_value)
    rows = []
    for (label, chain), _ in sorted(order.items(), key=lambda item: item[1]):
        value = totals[(label, chain)]
        reference = isolated[(label, chain)]
        fraction = value / reference if reference > 0 else 0.0
        if value <= min_delta:
            continue
        rows.append(
            {
                "residue": label,
                "side": "binder" if side_of_atom[_chain_index(chains, chain)] == 0 else "target",
                "delta_sasa": value,
                "isolated_sasa": reference,
                "buried_fraction": min(max(fraction, 0.0), 1.0),
                "is_core": fraction >= core_fraction,
            }
        )
    return rows


def _chain_index(chains: list[str], chain: str) -> int:
    try:
        return chains.index(chain)
    except ValueError:
        return 0


class StructureInterfaceCoreStep(Step):
    """Classify interface residues into rim and core from buried surface area."""

    provider = "biopipe-core"

    parameters_file = "structure_interface_core.StructureInterfaceCoreStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "id": "structure_interface_core",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface core residues",
        "description": (
            "Compute the per-residue buried surface area of a protein complex and "
            "classify interface residues as rim or core by the fraction of their "
            "isolated SASA that becomes buried on complex formation."
        ),
        "category": "Structure",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
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
        params = ctx.step_params
        (atoms,) = inputs
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        out_name = str(params.get("output") or "core")
        core_fraction = float(params.get("core_fraction") or 0.5)
        probe_radius = float(params.get("probe_radius") or 1.4)
        n_points = int(params.get("n_points") or 92)
        if not 0.0 < core_fraction <= 1.0:
            raise StepError("structure_interface_core: core_fraction must be in (0, 1]")
        if atom_dim not in atoms.dims or field_dim not in atoms.dims:
            raise StepError(
                f"structure_interface_core: expected dims [{atom_dim}, {field_dim}], "
                f"got {atoms.dims}"
            )
        if atoms.data.shape[0] == 0:
            raise StepError("structure_interface_core: the structure form is empty")
        for name in ("x", "y", "z", "chain", "resname", "residue_number", "element"):
            if not has_column(atoms, field_dim, name):
                raise StepError(f"structure_interface_core: no '{name}' column")

        coordinates = np.stack(
            [_column(atoms, field_dim, name) for name in ("x", "y", "z")], axis=1
        )
        elements = [
            _decode(atoms, field_dim, "element", value)
            for value in _column(atoms, field_dim, "element")
        ]
        chains = [
            _decode(atoms, field_dim, "chain", value)
            for value in _column(atoms, field_dim, "chain")
        ]
        labels = _residue_labels(atoms, field_dim)
        heavy = np.array([element.upper() not in {"H", "D"} for element in elements])
        if heavy.sum() < 2:
            raise StepError("structure_interface_core: the structure has no heavy atoms")
        if len(set(chains)) < 2:
            raise StepError(
                "structure_interface_core: the complex needs at least two chains, got "
                f"{sorted(set(chains))}"
            )
        binder_chains, target_chains = pick_chain_sides(
            set(chains),
            str(params.get("binder_chains") or ""),
            str(params.get("target_chains") or ""),
            "structure_interface_core",
        )
        side_masks = [
            np.array([chain in binder_chains for chain in chains]),
            np.array([chain in target_chains for chain in chains]),
        ]
        side_of_atom = np.where(side_masks[0], 0, 1)
        radii = vdw_radii(elements)
        complex_sasa, isolated = relative_sasa(
            coordinates, radii, side_masks, probe_radius=probe_radius, n_points=n_points
        )
        total_isolated = isolated[0] + isolated[1]
        delta = total_isolated - complex_sasa

        rows = core_rows(
            labels,
            chains,
            delta,
            total_isolated,
            side_of_atom,
            core_fraction=core_fraction,
        )
        if not rows:
            raise StepError(
                "structure_interface_core: no residue buries surface area between the "
                "selected sides; check binder_chains/target_chains"
            )
        data = np.asarray(
            [
                [
                    row["delta_sasa"],
                    row["isolated_sasa"],
                    row["buried_fraction"],
                    1.0 if row["is_core"] else 0.0,
                ]
                for row in rows
            ],
            dtype=np.float32,
        )
        form = Form(
            data,
            dims=["residue", "statistic"],
            labels={
                "residue": {row["residue"]: index for index, row in enumerate(rows)},
                "statistic": {
                    "delta_sasa": 0,
                    "isolated_sasa": 1,
                    "buried_fraction": 2,
                    "is_core": 3,
                },
            },
            info={
                "missing_code": np.nan,
                "n_interface": len(rows),
                "n_core": sum(1 for row in rows if row["is_core"]),
                "n_rim": sum(1 for row in rows if not row["is_core"]),
                "binder_chains": binder_chains,
                "target_chains": target_chains,
                "core_fraction": core_fraction,
                "probe_radius": probe_radius,
                "sides": [row["side"] for row in rows],
            },
        )
        ctx[out_name] = form
        self._export_data = form

    def export(self, ctx) -> dict:
        form = self._export_data
        return {
            "operator": "structure_interface_core",
            "n_interface": int(form.info["n_interface"]),
            "n_core": int(form.info["n_core"]),
        }
