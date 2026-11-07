"""Redesign interface hotspots with ProteinMPNN fixed positions."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._protein_common import decode_column, heavy_atom_mask, residue_labels
from ._structure_common import atom_coords, field_columns, pick_chain_sides, residue_numbers
from .interface_hotspots import contact_statistics
from .proteinmpnn_masked_design import mask_payload, pdb_chains, run_masked_designer

_STATISTICS = ("score", "global_score")


def hotspot_table(
    labels: np.ndarray,
    chains: np.ndarray,
    numbers: np.ndarray,
    binder_chains: list[str],
    counts: np.ndarray,
    distances: np.ndarray,
    *,
    min_contacts: int = 1,
) -> list[dict]:
    """Aggregate binder contact counts per residue and rank them."""

    totals: dict[str, int] = {}
    closest: dict[str, float] = {}
    chain_of: dict[str, str] = {}
    number_of: dict[str, int] = {}
    for label, chain, number, count, distance in zip(labels, chains, numbers, counts, distances):
        if chain not in binder_chains:
            continue
        totals[label] = totals.get(label, 0) + int(count)
        closest[label] = min(closest.get(label, np.inf), float(distance))
        chain_of[label] = chain
        number_of[label] = int(number)
    rows = [
        {
            "label": label,
            "chain": chain_of[label],
            "number": number_of[label],
            "n_contacts": totals[label],
            "min_distance": closest[label],
        }
        for label in totals
        if totals[label] >= min_contacts
    ]
    rows.sort(key=lambda row: (-row["n_contacts"], row["chain"], row["number"]))
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def hotspot_mask(rows: list[dict], top_n: int = 0) -> dict[str, list[int]]:
    """Turn ranked residues into ``{chain: [author numbers]}``."""

    selected = rows if top_n <= 0 else rows[:top_n]
    mask: dict[str, list[int]] = {}
    for row in selected:
        mask.setdefault(row["chain"], []).append(int(row["number"]))
    for chain in mask:
        mask[chain] = sorted(set(mask[chain]))
    return mask


class ProteinmpnnHotspotMaskedDesignStep(Step):
    """Design the hotspot residues of a binder-target interface."""

    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_hotspot_masked_design.ProteinmpnnHotspotMaskedDesignStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_hotspot_masked_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Hotspot-masked design",
        "description": (
            "Rank binder-target interface residues by contact density, keep the "
            "top hotspots as the only designable positions and run the official "
            "ProteinMPNN runner with every other residue fixed."
        ),
        "category": "Machine Learning",
        "icon": "ShareNetwork",
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
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")).strip() or "atom"
        field_dim = str(params.get("field_dim", "field")).strip() or "field"
        structure_text = str(params.get("structure_path") or "").strip()
        binder_text = str(params.get("binder_chains") or "").strip()
        target_text = str(params.get("target_chains") or "").strip()
        cutoff = float(params.get("cutoff") if params.get("cutoff") is not None else 5.0)
        min_contacts = int(params.get("min_contacts") or 1)
        top_n = int(params.get("top_n") or 0)
        out_name = params.get("output", self.name)

        if not structure_text:
            raise StepError("proteinmpnn_hotspot_masked_design: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_hotspot_masked_design: structure_path {structure} is not a file")
        if structure.suffix.lower() not in {".pdb", ".ent"}:
            raise StepError("proteinmpnn_hotspot_masked_design: structure_path must name a .pdb file")
        if not 3.0 <= cutoff <= 10.0:
            raise StepError("proteinmpnn_hotspot_masked_design: cutoff must be between 3 and 10 angstrom")
        if min_contacts < 1:
            raise StepError("proteinmpnn_hotspot_masked_design: min_contacts must be at least 1")
        if top_n < 0:
            raise StepError("proteinmpnn_hotspot_masked_design: top_n must not be negative")

        form = inputs[0]
        field_columns(form, field_dim, ("x", "y", "z", "chain", "resname", "residue_number", "element"))
        heavy = heavy_atom_mask(form, field_dim)
        chains = np.asarray([str(value).strip() for value in decode_column(form, field_dim, "chain")])
        present = set(chains[heavy])
        if len(present) < 2:
            raise StepError("proteinmpnn_hotspot_masked_design: the complex needs at least two chains")
        binder_chains, target_chains = pick_chain_sides(
            present, binder_text, target_text, "proteinmpnn_hotspot_masked_design"
        )
        binder_mask = heavy & np.isin(chains, binder_chains)
        target_mask = heavy & np.isin(chains, target_chains)
        if not binder_mask.any() or not target_mask.any():
            raise StepError(
                "proteinmpnn_hotspot_masked_design: binder and target must both carry heavy atoms"
            )
        coordinates = atom_coords(form, field_dim)
        labels = residue_labels(form, field_dim)
        numbers = residue_numbers(form, field_dim)
        counts, distances = contact_statistics(
            coordinates[binder_mask], coordinates[target_mask], cutoff
        )
        rows = hotspot_table(
            labels[binder_mask],
            chains[binder_mask],
            numbers[binder_mask],
            binder_chains,
            counts,
            distances,
            min_contacts=min_contacts,
        )
        if not rows:
            raise StepError(
                "proteinmpnn_hotspot_masked_design: no binder residue contacts the "
                f"target within {cutoff:g} angstrom"
            )
        if top_n and top_n > len(rows):
            raise StepError(
                "proteinmpnn_hotspot_masked_design: top_n "
                f"{top_n} exceeds the {len(rows)} interface residue(s)"
            )
        mask = hotspot_mask(rows, top_n)
        chains_in_file = pdb_chains(structure)
        for chain, numbers in mask.items():
            if chain not in chains_in_file:
                raise StepError(
                    f"proteinmpnn_hotspot_masked_design: chain {chain} is absent from {structure}"
                )
            missing = [number for number in numbers if number not in set(chains_in_file[chain])]
            if missing:
                raise StepError(
                    "proteinmpnn_hotspot_masked_design: residue(s) "
                    + ", ".join(f"{chain}:{number}" for number in missing)
                    + " are not author residue numbers of the structure file"
                )
        payload = mask_payload(mask, chains_in_file, structure.stem)
        records = run_masked_designer(params, structure, " ".join(binder_chains), payload)
        if not records:
            raise StepError("proteinmpnn_hotspot_masked_design: the designer generated no sequence")
        data = np.asarray(
            [(float(record["score"]), float(record["global_score"])) for record in records],
            dtype=np.float32,
        )
        form_out = Form(
            data=data,
            dims=["design", "statistic"],
            labels={
                "design": {f"design{index + 1}": index for index in range(len(records))},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "sequences": [record["sequence"] for record in records],
                "hotspots": [row["label"] for row in rows[: top_n or len(rows)]],
                "mask": mask,
                "n_hotspots": sum(len(numbers) for numbers in mask.values()),
                "n_interface": len(rows),
                "binder_chains": binder_chains,
                "target_chains": target_chains,
                "cutoff": cutoff,
                "structure_path": str(structure),
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_designs": len(records),
            "n_hotspots": int(sum(len(numbers) for numbers in mask.values())),
            "n_interface": len(rows),
            "binder_chains": binder_chains,
            "target_chains": target_chains,
        }
        print(
            f"[{self.name}] {len(records)} design(s) over "
            f"{sum(len(numbers) for numbers in mask.values())} hotspot(s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
