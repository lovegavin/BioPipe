"""Paratope residues: CDR positions that contact the antigen."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import (
    column_index,
    decode_column,
    heavy_atom_mask,
    residue_labels,
)
from ._structure_common import atom_coords, field_columns, pick_chain_sides
from .antibody_cdr_kabat import REGIONS, kabat_regions
from .interface_hotspots import contact_statistics

_THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}

_STATISTICS = ("n_contacts", "min_distance", "is_paratope", "cdr_index")


def chain_sequences(form: Form, field_dim: str) -> dict[str, tuple[list[str], str]]:
    """Return ``chain -> (residue labels in order, one-letter sequence)``."""

    labels = residue_labels(form, field_dim)
    chains = np.asarray([str(value).strip() for value in decode_column(form, field_dim, "chain")])
    order: dict[str, list[str]] = {}
    residues: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for label, chain in zip(labels, chains):
        chain = chain or "_"
        order.setdefault(chain, [])
        residues.setdefault(chain, [])
        seen.setdefault(chain, set())
        if label in seen[chain]:
            continue
        seen[chain].add(label)
        order[chain].append(label)
        resname = label.split(":")[1]
        residues[chain].append(_THREE_TO_ONE.get(resname, "X"))
    return {chain: (order[chain], "".join(residues[chain])) for chain in order}


def residue_cdr_map(sequence: str) -> dict[int, tuple[str, int]]:
    """Map a 1-based sequence position to ``(cdr name, region index)``."""

    result: dict[int, tuple[str, int]] = {}
    for index, (name, start, end, _residues) in enumerate(kabat_regions(sequence), start=1):
        if "CDR" not in name:
            continue
        for position in range(start, end + 1):
            result[position] = (name, index)
    return result


def paratope_rows(
    labels: np.ndarray,
    label_positions: dict[str, int],
    chain_of_label: dict[str, str],
    cdr_maps: dict[str, dict[int, tuple[str, int]]],
    counts: np.ndarray,
    min_distances: np.ndarray,
    *,
    min_contacts: int = 1,
) -> list[dict]:
    """Aggregate per-atom contact data into per-residue paratope rows."""

    totals: dict[str, int] = {}
    closest: dict[str, float] = {}
    for label, count, distance in zip(labels, counts, min_distances):
        totals[label] = totals.get(label, 0) + int(count)
        closest[label] = min(closest.get(label, np.inf), float(distance))
    rows: list[dict] = []
    for label in sorted(totals):
        chain = chain_of_label.get(label, "")
        position = label_positions.get(label)
        if chain not in cdr_maps or position is None:
            continue
        cdr = cdr_maps.get(chain, {}).get(position)
        if totals[label] < min_contacts:
            continue
        rows.append(
            {
                "residue": label,
                "n_contacts": totals[label],
                "min_distance": closest[label],
                "cdr": cdr[0] if cdr else "framework",
                "cdr_index": cdr[1] if cdr else 0,
                "is_paratope": 1 if cdr else 0,
            }
        )
    rows.sort(key=lambda row: (row["is_paratope"], row["n_contacts"], row["residue"]), reverse=True)
    return rows


class StructureParatopePredictStep(Step):
    """Report CDR residues that touch the antigen in a complex."""

    provider = "operon-core"
    parameters_file = "structure_paratope_predict.StructureParatopePredictStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_paratope_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Paratope prediction",
        "description": (
            "Annotate the Kabat CDR spans of the binder chain(s), count antigen "
            "contacts per residue and report which CDR residues form the paratope."
        ),
        "category": "Structure",
        "icon": "Intersect",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {"encoders": {"type": "object", "optional": True}},
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
        "dependencies": ["numpy>=1.24", "scipy>=1.10", "biopython>=1.80"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        binder_text = str(params.get("binder_chains") or "").strip()
        target_text = str(params.get("target_chains") or "").strip()
        cutoff = float(params.get("cutoff") if params.get("cutoff") is not None else 5.0)
        min_contacts = int(params.get("min_contacts") or 1)
        out_name = params.get("output", self.name)

        if not 3.0 <= cutoff <= 10.0:
            raise StepError("structure_paratope_predict: cutoff must be between 3 and 10 angstrom")
        if min_contacts < 1:
            raise StepError("structure_paratope_predict: min_contacts must be at least 1")
        form = inputs[0]
        field_columns(form, field_dim, ("x", "y", "z", "chain", "resname", "residue_number", "element"))
        heavy = heavy_atom_mask(form, field_dim)
        if heavy.sum() < 2:
            raise StepError("structure_paratope_predict: the structure has no heavy atoms")
        chains = np.asarray([str(value).strip() for value in decode_column(form, field_dim, "chain")])
        present = set(chains[heavy])
        if len(present) < 2:
            raise StepError("structure_paratope_predict: the complex needs at least two chains")
        binder_chains, target_chains = pick_chain_sides(present, binder_text, target_text, "structure_paratope_predict")
        binder_mask = heavy & np.isin(chains, binder_chains)
        target_mask = heavy & np.isin(chains, target_chains)
        if not binder_mask.any() or not target_mask.any():
            raise StepError("structure_paratope_predict: binder and target must both carry heavy atoms")
        coordinates = atom_coords(form, field_dim)
        counts, distances = contact_statistics(
            coordinates[binder_mask], coordinates[target_mask], cutoff
        )
        labels = residue_labels(form, field_dim)
        label_map = chain_sequences(form, field_dim)
        label_positions: dict[str, int] = {}
        chain_of_label: dict[str, str] = {}
        cdr_maps: dict[str, dict[int, tuple[str, int]]] = {}
        for chain in binder_chains:
            if chain not in label_map:
                continue
            order, sequence = label_map[chain]
            try:
                cdr_maps[chain] = residue_cdr_map(sequence)
            except StepError as error:
                raise StepError(
                    f"structure_paratope_predict: chain {chain} is not a VH/VHH domain ({error})"
                ) from error
            for position, label in enumerate(order, start=1):
                chain_of_label[label] = chain
                label_positions[label] = position
        rows = paratope_rows(
            labels[binder_mask],
            label_positions,
            chain_of_label,
            cdr_maps,
            counts,
            distances,
            min_contacts=min_contacts,
        )
        if not rows:
            raise StepError(
                "structure_paratope_predict: no binder residue contacts the target "
                f"within {cutoff:g} angstrom"
            )
        data = np.asarray(
            [
                (
                    float(row["n_contacts"]),
                    float(row["min_distance"]),
                    float(row["is_paratope"]),
                    float(row["cdr_index"]),
                )
                for row in rows
            ],
            dtype=np.float32,
        )
        form_out = Form(
            data=data,
            dims=["residue", "statistic"],
            labels={
                "residue": {row["residue"]: index for index, row in enumerate(rows)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "binder_chains": binder_chains,
                "target_chains": target_chains,
                "cutoff": cutoff,
                "min_contacts": min_contacts,
                "n_interface": len(rows),
                "n_paratope": sum(row["is_paratope"] for row in rows),
                "paratope_residues": [row["residue"] for row in rows if row["is_paratope"]],
                "cdr_counts": {
                    name: sum(1 for row in rows if row["cdr"] == name)
                    for name in REGIONS
                    if name.startswith("CDR")
                },
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_interface": len(rows),
            "n_paratope": int(sum(row["is_paratope"] for row in rows)),
            "binder_chains": binder_chains,
            "target_chains": target_chains,
        }
        print(
            f"[{self.name}] {len(rows)} interface residue(s), "
            f"{sum(row['is_paratope'] for row in rows)} paratope residue(s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
