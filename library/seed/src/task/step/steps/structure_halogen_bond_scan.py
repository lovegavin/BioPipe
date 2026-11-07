"""Detect intramolecular halogen bonds from full-atom structure coordinates."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.base import Step

from .structure_helix_helix_angle import _column, _text_column

_HALOGENS = {"F", "CL", "BR", "I"}
_ACCEPTORS = {"O", "N", "S"}
_CARBON = {"C"}


def _residue(label: str) -> str:
    return label.rsplit(":", 1)[0] if ":" in label else label


def atom_table(form: Form, field_dim: str) -> dict[str, np.ndarray]:
    atom_names = _text_column(form, field_dim, "atom_name")
    resnames = _text_column(form, field_dim, "resname")
    chains = _text_column(form, field_dim, "chain")
    numbers = _column(form, field_dim, "residue_number")
    elements = _text_column(form, field_dim, "element")
    coords = np.column_stack([_column(form, field_dim, axis) for axis in ("x", "y", "z")])
    labels = [
        f"{chains[index]}:{resnames[index]}:{int(round(float(numbers[index])))}:{atom_names[index]}"
        for index in range(len(coords))
    ]
    return {
        "labels": np.array(labels, dtype=object),
        "elements": np.array([str(element).strip().upper() for element in elements], dtype=object),
        "coords": coords.astype(np.float64),
        "residues": np.array([_residue(label) for label in labels], dtype=object),
    }


def halogen_donors(table: dict[str, np.ndarray], bond_length: float = 2.2) -> list[dict]:
    """Halogens with a carbon neighbour within the covalent bond window."""
    donors: list[dict] = []
    coords = table["coords"]
    elements = table["elements"]
    carbons = np.flatnonzero(np.isin(elements, list(_CARBON)))
    for index in np.flatnonzero(np.isin(elements, list(_HALOGENS))):
        if not carbons.size:
            continue
        distances = np.linalg.norm(coords[carbons] - coords[index], axis=1)
        nearest = int(carbons[int(np.argmin(distances))])
        if float(distances.min()) <= float(bond_length):
            donors.append(
                {
                    "index": int(index),
                    "carbon": nearest,
                    "label": str(table["labels"][index]),
                    "residue": str(table["residues"][index]),
                }
            )
    return donors


def halogen_bonds(
    table: dict[str, np.ndarray],
    *,
    max_distance: float = 4.0,
    min_angle: float = 140.0,
    bond_length: float = 2.2,
) -> list[dict]:
    """Return halogen bonds with distance and C-X...Y angle."""
    coords = table["coords"]
    elements = table["elements"]
    donors = halogen_donors(table, bond_length)
    acceptors = np.flatnonzero(np.isin(elements, list(_ACCEPTORS)))
    bonds: list[dict] = []
    for donor in donors:
        for target in acceptors:
            target = int(target)
            if str(table["residues"][target]) == donor["residue"]:
                continue
            vector = coords[target] - coords[donor["index"]]
            distance = float(np.linalg.norm(vector))
            if distance <= 0.0 or distance > float(max_distance):
                continue
            carbon_vector = coords[donor["carbon"]] - coords[donor["index"]]
            carbon_norm = float(np.linalg.norm(carbon_vector))
            if carbon_norm <= 0.0:
                continue
            cosine = float(np.dot(carbon_vector, vector) / (carbon_norm * distance))
            angle = float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
            if angle < float(min_angle):
                continue
            bonds.append(
                {
                    "donor": donor["label"],
                    "acceptor": str(table["labels"][target]),
                    "distance": distance,
                    "angle_deg": angle,
                }
            )
    bonds.sort(key=lambda bond: (-bond["angle_deg"], bond["distance"]))
    return bonds


class StructureHalogenBondScanStep(Step):
    provider = "operon-core"
    parameters_file = "structure_halogen_bond_scan.StructureHalogenBondScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "structure_halogen_bond_scan",
        "kind": "operator",
        "title": "Halogen bond scan",
        "description": "Scan a full-atom structure for halogen bonds: carbon-halogen donors against oxygen, nitrogen or sulfur acceptors using distance and C-X...Y angle criteria.",
        "category": "Machine Learning",
        "icon": "Unite",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim", "default": "atom"}, {"param": "field_dim", "default": "field"}],
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    _STATISTICS = ("distance", "angle_deg")

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("structure_halogen_bond_scan: a PDB form input is required")
        form = inputs[0]
        atom_dim = str(ctx.step_params.get("atom_dim", "atom") or "atom")
        field_dim = str(ctx.step_params.get("field_dim", "field") or "field")
        bond_dim = str(ctx.step_params.get("bond_dim", "bond") or "bond")
        out_name = ctx.step_params.get("output", "halogen_bonds") or "halogen_bonds"
        max_distance = ctx.step_params.get("max_distance", 4.0)
        min_angle = ctx.step_params.get("min_angle", 140.0)
        bond_length = ctx.step_params.get("bond_length", 2.2)

        if list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                f"structure_halogen_bond_scan: a PDB form with dims [{atom_dim}, {field_dim}] is required, "
                f"got {list(form.dims)}"
            )
        if not isinstance(max_distance, (int, float)) or not 2.5 <= float(max_distance) <= 6.0:
            raise StepError("structure_halogen_bond_scan: max_distance must be between 2.5 and 6.0 angstrom")
        if not isinstance(min_angle, (int, float)) or not 90.0 <= float(min_angle) <= 180.0:
            raise StepError("structure_halogen_bond_scan: min_angle must be between 90 and 180 degrees")
        if not isinstance(bond_length, (int, float)) or not 1.4 <= float(bond_length) <= 3.0:
            raise StepError("structure_halogen_bond_scan: bond_length must be between 1.4 and 3.0 angstrom")

        table = atom_table(form, field_dim)
        if not np.any(np.isin(table["elements"], list(_HALOGENS))):
            raise StepError("structure_halogen_bond_scan: the structure form has no halogen atoms to scan")
        bonds = halogen_bonds(
            table,
            max_distance=float(max_distance),
            min_angle=float(min_angle),
            bond_length=float(bond_length),
        )
        if not bonds:
            raise StepError(
                "structure_halogen_bond_scan: no halogen bond satisfies the distance and angle criteria"
            )

        matrix = np.asarray([[bond["distance"], bond["angle_deg"]] for bond in bonds], dtype=np.float32)
        row_labels = [f"{bond['donor']}->{bond['acceptor']}" for bond in bonds]
        out = Form(
            data=matrix,
            dims=[bond_dim, "statistic"],
            labels={
                bond_dim: {label: index for index, label in enumerate(row_labels)},
                "statistic": {name: index for index, name in enumerate(self._STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_bonds": len(bonds),
                "max_distance": float(max_distance),
                "min_angle": float(min_angle),
                "bond_length": float(bond_length),
                "statistics": list(self._STATISTICS),
                "bonds": bonds,
                "unit": "angstrom",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_bonds": len(bonds),
            "mean_distance": float(np.mean(matrix[:, 0])),
            "mean_angle_deg": float(np.mean(matrix[:, 1])),
            "max_distance": float(max_distance),
            "min_angle": float(min_angle),
        }
        print(f"[structure_halogen_bond_scan] {len(bonds)} halogen bonds")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
