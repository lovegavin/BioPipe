"""Salt bridges between charged amino-acid side chains."""
from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from ._protein_common import column_index, decode_column, has_column

_ANIONIC_ATOMS = {"ASP": ("OD1", "OD2"), "GLU": ("OE1", "OE2")}
_CATIONIC_ATOMS = {
    "LYS": ("NZ",),
    "ARG": ("CZ", "NH1", "NH2"),
    "HIS": ("ND1", "NE2"),
}
_STATISTICS = ("distance",)


def charged_centroids(
    coordinates: np.ndarray,
    resnames: np.ndarray,
    atom_names: np.ndarray,
    labels: np.ndarray,
) -> list[dict]:
    """Centroid of the charged group of every anionic/cationic residue."""
    grouped: dict[str, dict] = {}
    for index in range(len(resnames)):
        resname = str(resnames[index]).upper()
        atom = str(atom_names[index]).upper()
        group = None
        if resname in _ANIONIC_ATOMS:
            group = "anion"
            allowed = _ANIONIC_ATOMS[resname]
        elif resname in _CATIONIC_ATOMS:
            group = "cation"
            allowed = _CATIONIC_ATOMS[resname]
        else:
            continue
        if atom not in allowed:
            continue
        label = str(labels[index])
        entry = grouped.setdefault(
            label,
            {"label": label, "resname": resname, "group": group, "points": []},
        )
        entry["points"].append(coordinates[index])
    rows: list[dict] = []
    for entry in grouped.values():
        points = np.asarray(entry["points"], dtype=np.float64)
        rows.append(
            {
                "label": entry["label"],
                "resname": entry["resname"],
                "group": entry["group"],
                "centroid": points.mean(axis=0),
            }
        )
    return sorted(rows, key=lambda row: row["label"])


def salt_bridges(
    residues: list[dict], max_distance: float
) -> list[dict]:
    """Pair anionic and cationic centroids closer than ``max_distance``."""
    anions = [row for row in residues if row["group"] == "anion"]
    cations = [row for row in residues if row["group"] == "cation"]
    pairs: list[dict] = []
    for anion in anions:
        for cation in cations:
            distance = float(
                np.linalg.norm(anion["centroid"] - cation["centroid"])
            )
            if distance > max_distance:
                continue
            left, right = anion["label"], cation["label"]
            pair = tuple(sorted((left, right)))
            pairs.append(
                {
                    "bridge": f"{pair[0]}-{pair[1]}",
                    "distance": distance,
                    "anion": left,
                    "cation": right,
                }
            )
    return sorted(pairs, key=lambda row: (row["distance"], row["bridge"]))


class StructureSaltBridgesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_salt_bridges.StructureSaltBridgesStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_salt_bridges",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure salt bridges",
        "category": "Machine Learning",
        "icon": "Unite",
        "description": (
            "Find salt bridges from the distance between charged side-chain "
            "group centroids of ASP/GLU and LYS/ARG/HIS residues."
        ),
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
                    "info": {"missing_code": {"type": ["number", "null"]}},
                }
            ],
            "output": {
                "version": 1,
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
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
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        out_name = params["output"]
        raw_distance = params.get("max_distance")
        max_distance = 4.0 if raw_distance is None else float(raw_distance)
        if not 2.0 <= max_distance <= 10.0:
            raise StepError(
                "structure_salt_bridges: max_distance must be between 2.0 and 10.0 angstrom"
            )
        if not inputs:
            raise StepError("structure_salt_bridges: a PDB form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [atom_dim, field_dim]:
            raise StepError(
                "structure_salt_bridges: a PDB form with dims "
                f"[{atom_dim}, {field_dim}] is required, got {list(form.dims)}"
            )
        for name in ("x", "y", "z", "resname", "atom_name", "chain", "residue_number"):
            if not has_column(form, field_dim, name):
                raise StepError(
                    f"structure_salt_bridges: the PDB form has no '{name}' column"
                )
        resnames = decode_column(form, field_dim, "resname")
        atom_names = decode_column(form, field_dim, "atom_name")
        chains = decode_column(form, field_dim, "chain")
        numbers = decode_column(form, field_dim, "residue_number")
        labels = np.array(
            [f"{chains[i]}:{resnames[i]}:{numbers[i]}" for i in range(len(resnames))],
            dtype=object,
        )
        columns = [column_index(form, field_dim, axis) for axis in ("x", "y", "z")]
        coordinates = np.asarray(form.data, dtype=np.float64)[:, columns]
        if not np.isfinite(coordinates).all():
            raise StepError(
                "structure_salt_bridges: the structure contains non-finite coordinates"
            )
        residues = charged_centroids(coordinates, resnames, atom_names, labels)
        if not residues:
            raise StepError(
                "structure_salt_bridges: no charged residues (ASP, GLU, LYS, ARG, HIS) "
                "were found in the structure form"
            )
        pairs = salt_bridges(residues, max_distance)
        anions = sorted(row["label"] for row in residues if row["group"] == "anion")
        cations = sorted(row["label"] for row in residues if row["group"] == "cation")
        inter = 0
        for pair in pairs:
            left_chain = pair["anion"].split(":")[0]
            right_chain = pair["cation"].split(":")[0]
            if left_chain != right_chain:
                inter += 1
        data = np.asarray([[pair["distance"] for pair in pairs]], dtype=np.float32)
        data = data.reshape(len(pairs), 1)
        output = Form(
            data=data,
            dims=["bridge", "statistic"],
            labels={
                "bridge": {pair["bridge"]: index for index, pair in enumerate(pairs)},
                "statistic": {"distance": 0},
            },
            info={
                "missing_code": np.nan,
                "bridges": [
                    {
                        "bridge": pair["bridge"],
                        "distance": pair["distance"],
                        "kind": (
                            "inter"
                            if pair["anion"].split(":")[0]
                            != pair["cation"].split(":")[0]
                            else "intra"
                        ),
                    }
                    for pair in pairs
                ],
                "n_bridges": len(pairs),
                "n_intra": len(pairs) - inter,
                "n_inter": inter,
                "anions": anions,
                "cations": cations,
                "max_distance": max_distance,
                "unit": "A",
            },
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_bridges": len(pairs),
            "n_intra": len(pairs) - inter,
            "n_inter": inter,
            "anions": anions,
            "cations": cations,
            "max_distance": max_distance,
        }
        print(
            f"[structure_salt_bridges] {len(pairs)} bridge(s) between "
            f"{len(anions)} anion(s) and {len(cations)} cation(s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
