"""Backbone hydrogen-bond detection with a Kabsch-Sander energy model."""

from __future__ import annotations

import math

import numpy as np

from src.core.forms.form import Form
from src.task.context.base import Context
from src.core.errors import StepError
from src.task.step.base import Step

#: Kabsch-Sander electrostatic factor, 0.084 * 332 (kcal/mol per Angstrom).
ENERGY_FACTOR = 0.084 * 332.0

#: Backbone atoms required to place the amide hydrogen and the carbonyl group.
_REQUIRED_ATOMS = ("N", "C", "O")

#: Proline has no amide hydrogen and therefore never donates a backbone bond.
_DONOR_EXCLUDED = {"PRO"}

_STATISTICS = ("donors", "acceptors", "min_energy")


def _field_labels(form: Form, field_dim: str) -> dict:
    labels = form.labels.get(field_dim)
    if not isinstance(labels, dict):
        raise StepError("structure_hbonds: the PDB form needs named columns on the field dimension")
    return labels


def _column(form: Form, field_dim: str, labels: dict, name: str) -> np.ndarray:
    if name not in labels:
        raise StepError(f"structure_hbonds: the PDB form has no '{name}' column")
    index = list(form.dims).index(field_dim)
    return np.asarray(form.data.take(int(labels[name]), axis=index), dtype=np.float64)


def _text_column(form: Form, field_dim: str, labels: dict, name: str) -> np.ndarray:
    values = _column(form, field_dim, labels, name)
    encoders = (form.info.get("encoders") or {}).get(field_dim) or {}
    encoder = encoders.get(name)
    if encoder is not None:
        return np.asarray(encoder.inverse_transform(values), dtype=object)
    if np.all(np.isfinite(values)) and np.allclose(values, np.rint(values)):
        return np.asarray([str(int(value)) for value in np.rint(values)], dtype=object)
    return np.asarray([str(value) for value in values], dtype=object)


def _coordinates(form: Form, atom_dim: str, field_dim: str, labels: dict, index: int) -> np.ndarray:
    dim = list(form.dims).index(atom_dim)
    row = np.asarray(np.take(form.data, index, axis=dim), dtype=np.float64)
    return np.asarray([row[int(labels[name])] for name in ("x", "y", "z")], dtype=np.float64)


def _residues(form: Form, atom_dim: str, field_dim: str) -> list[dict]:
    """Group atoms into residues that carry a complete N, C, O backbone."""
    labels = _field_labels(form, field_dim)
    chain = _text_column(form, field_dim, labels, "chain")
    resname = _text_column(form, field_dim, labels, "resname")
    number = _column(form, field_dim, labels, "residue_number")
    if "insertion_code" in labels:
        insertion = _text_column(form, field_dim, labels, "insertion_code")
    else:
        insertion = np.asarray([""] * len(chain), dtype=object)
    if "atom_name" in labels:
        atom_name = _text_column(form, field_dim, labels, "atom_name")
    else:
        atom_name = np.asarray([""] * len(chain), dtype=object)

    order: list[tuple] = []
    groups: dict[tuple, dict] = {}
    for index in range(len(chain)):
        key = (str(chain[index]), int(round(float(number[index]))), str(insertion[index]).strip("_ "))
        if key not in groups:
            groups[key] = {"chain": key[0], "number": key[1], "insertion": key[2], "resname": str(resname[index]).upper(), "atoms": {}}
            order.append(key)
        groups[key]["atoms"].setdefault(str(atom_name[index]).strip(), _coordinates(form, atom_dim, field_dim, labels, index))

    residues = []
    for key in order:
        entry = groups[key]
        if not all(name in entry["atoms"] for name in _REQUIRED_ATOMS):
            continue
        entry["coords"] = {name: entry["atoms"][name] for name in _REQUIRED_ATOMS}
        label = f"{entry['chain']}:{entry['resname']}:{entry['number']}{entry['insertion']}"
        entry["label"] = label
        residues.append(entry)
    return residues


def hydrogen_positions(residues: list[dict]) -> list:
    """Place each amide hydrogen antiparallel to the preceding carbonyl."""
    hydrogens: list = [None] * len(residues)
    for index in range(1, len(residues)):
        previous = residues[index - 1]
        current = residues[index]
        if previous["chain"] != current["chain"]:
            continue
        direction = previous["coords"]["C"] - previous["coords"]["O"]
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-6:
            continue
        hydrogens[index] = current["coords"]["N"] + direction / norm
    return hydrogens


def hbond_energy(donor: dict, acceptor: dict, hydrogen: np.ndarray) -> float:
    """Kabsch-Sander electrostatic interaction energy in kcal/mol."""
    r_on = float(np.linalg.norm(acceptor["coords"]["O"] - donor["coords"]["N"]))
    r_ch = float(np.linalg.norm(acceptor["coords"]["C"] - hydrogen))
    r_oh = float(np.linalg.norm(acceptor["coords"]["O"] - hydrogen))
    r_cn = float(np.linalg.norm(acceptor["coords"]["C"] - donor["coords"]["N"]))
    if min(r_on, r_ch, r_oh, r_cn) < 0.5:
        return math.inf
    return ENERGY_FACTOR * (1.0 / r_on + 1.0 / r_ch - 1.0 / r_oh - 1.0 / r_cn)


class StructureHbondsStep(Step):
    provider = "operon-core"
    parameters_file = "structure_hbonds.StructureHbondsStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_hbonds",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Backbone Hydrogen Bonds",
        "description": (
            "Find backbone N-H...O=C hydrogen bonds with the Kabsch-Sander "
            "electrostatic model and summarise donors, acceptors and the "
            "strongest interaction energy per residue."
        ),
        "category": "Machine Learning",
        "icon": "Unite",
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
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        form = inputs[0]
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom"))
        field_dim = str(params.get("field_dim", "field"))
        residue_dim = str(params.get("residue_dim", "residue"))
        threshold = float(params.get("energy_threshold", -0.5))
        max_distance = float(params.get("max_distance", 5.2))
        include_inter_chain = bool(params.get("include_inter_chain", False))
        output = str(params.get("output", "output"))

        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(f"structure_hbonds: a PDB form with dims [{atom_dim}, {field_dim}] is required")
        if not threshold < 0.0:
            raise StepError("structure_hbonds: energy_threshold must be negative")
        if not 1.5 <= max_distance <= 10.0:
            raise StepError("structure_hbonds: max_distance must be between 1.5 and 10.0 angstrom")

        residues = _residues(form, atom_dim, field_dim)
        if len(residues) < 3:
            raise StepError("structure_hbonds: at least three residues with N, C and O atoms are required")

        hydrogens = hydrogen_positions(residues)
        bonds = []
        donor_counts = [0] * len(residues)
        acceptor_counts = [0] * len(residues)
        min_energy = [math.nan] * len(residues)
        for i, donor in enumerate(residues):
            hydrogen = hydrogens[i]
            if hydrogen is None or donor["resname"] in _DONOR_EXCLUDED:
                continue
            for j, acceptor in enumerate(residues):
                if abs(i - j) < 2:
                    continue
                if not include_inter_chain and donor["chain"] != acceptor["chain"]:
                    continue
                if float(np.linalg.norm(acceptor["coords"]["O"] - donor["coords"]["N"])) > max_distance:
                    continue
                energy = hbond_energy(donor, acceptor, hydrogen)
                if not math.isfinite(energy) or energy >= threshold:
                    continue
                bonds.append((donor["label"], acceptor["label"], float(energy)))
                donor_counts[i] += 1
                acceptor_counts[j] += 1
                if math.isnan(min_energy[i]) or energy < min_energy[i]:
                    min_energy[i] = energy
                if math.isnan(min_energy[j]) or energy < min_energy[j]:
                    min_energy[j] = energy

        bonds.sort(key=lambda item: (item[2], item[0], item[1]))
        labels = [residue["label"] for residue in residues]
        data = np.asarray([[donor_counts[i], acceptor_counts[i], min_energy[i]] for i in range(len(residues))], dtype=np.float32)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "bonds": [[donor, acceptor, round(energy, 4)] for donor, acceptor, energy in bonds],
                "n_bonds": len(bonds),
                "n_residues": len(residues),
                "n_donor_residues": sum(1 for count in donor_counts if count),
                "n_acceptor_residues": sum(1 for count in acceptor_counts if count),
                "energy_threshold": threshold,
                "max_distance": max_distance,
                "include_inter_chain": include_inter_chain,
                "unit": "kcal/mol",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "residues": len(residues),
            "bonds": len(bonds),
            "donor_residues": out.info["n_donor_residues"],
            "acceptor_residues": out.info["n_acceptor_residues"],
            "energy_threshold": threshold,
            "max_distance": max_distance,
        }
        print(
            f"structure_hbonds: {len(residues)} residues, {len(bonds)} backbone bonds, "
            f"{out.info['n_donor_residues']} donor and {out.info['n_acceptor_residues']} acceptor residues"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
