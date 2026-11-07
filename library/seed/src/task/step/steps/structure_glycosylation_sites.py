"""Glycosylation sequon detection on a protein structure."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.reader import read_source
from src.task.step.base import Step

from ._protein_common import column_index, decode_column, heavy_atom_mask, residue_labels
from .interface_bsa import sasa_per_atom, vdw_radii
from .structure_paratope_predict import chain_sequences


_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}


def sequons(sequence: str, *, include_o_linked: bool = False) -> list[tuple[int, str, str]]:
    """Return (1-based position, motif, kind) for every glycan acceptor site."""

    sequence = str(sequence or "").upper()
    sites: list[tuple[int, str, str]] = []
    for index in range(len(sequence) - 2):
        if sequence[index] == "N" and sequence[index + 1] != "P" and sequence[index + 2] in "ST":
            sites.append((index + 1, sequence[index : index + 3], "N-linked"))
    if include_o_linked:
        for index, residue in enumerate(sequence):
            if residue in "ST":
                sites.append((index + 1, residue, "O-linked"))
    return sites


def residue_sasa(form: Form, atom_dim: str, field_dim: str) -> dict[str, tuple[float, int]]:
    """Mean per-atom SASA (A^2) and heavy atom count for every residue label."""

    elements = decode_column(form, field_dim, "element")
    mask = heavy_atom_mask(form, field_dim)
    if not mask.any():
        raise StepError("structure_glycosylation_sites: the structure form has no heavy atoms")
    coordinates = np.stack(
        [form.data[:, column_index(form, field_dim, axis)] for axis in "xyz"], axis=1
    )[mask]
    radii = vdw_radii(elements[mask])
    areas = sasa_per_atom(coordinates, radii)
    labels = residue_labels(form, field_dim)[mask]
    totals: dict[str, tuple[float, int]] = {}
    for label, area in zip(labels, areas.tolist()):
        total, count = totals.get(label, (0.0, 0))
        totals[label] = (total + float(area), count + 1)
    return {label: (total / count, count) for label, (total, count) in totals.items()}


class StructureGlycosylationSitesStep(Step):
    """Detect N-/O-linked glycosylation sequons and their surface exposure."""

    provider = "operon-core"
    parameters_file = (
        "structure_glycosylation_sites.StructureGlycosylationSitesStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_glycosylation_sites",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Glycosylation sites",
        "description": (
            "Report N-X-S/T (and optionally O-linked Ser/Thr) sequons of every "
            "protein chain together with the mean per-atom solvent "
            "exposure of the acceptor residue."
        ),
        "category": "Structure",
        "icon": "Scissors",
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
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")) or "atom"
        field_dim = str(params.get("field_dim", "field")) or "field"
        site_dim = str(params.get("site_dim", "site")) or "site"
        out_name = str(params.get("output", "sites")) or "sites"
        min_sasa = float(params.get("min_sasa", 10.0))
        include_o_linked = bool(params.get("include_o_linked", False))

        form = inputs[0]
        if form.dims[0] != atom_dim or form.dims[1] != field_dim:
            raise StepError(
                f"structure_glycosylation_sites: expected [{atom_dim}, {field_dim}], got {form.dims}"
            )
        sequences = chain_sequences(form, field_dim)
        if not sequences:
            raise StepError("structure_glycosylation_sites: the structure form carries no protein chain")
        exposure = residue_sasa(form, atom_dim, field_dim)

        rows: list[dict] = []
        for chain in sorted(sequences):
            chain_labels, sequence = sequences[chain]
            numbers = {label: int(label.rsplit(":", 1)[-1]) for label in chain_labels}
            for position, motif, kind in sequons(sequence, include_o_linked=include_o_linked):
                label = chain_labels[position - 1]
                resname = label.split(":")[1]
                mean_sasa, n_atoms = exposure.get(label, (0.0, 0))
                rows.append(
                    {
                        "site": label,
                        "position": int(numbers.get(label, position)),
                        "motif": motif,
                        "kind": kind,
                        "mean_sasa": mean_sasa,
                        "n_atoms": n_atoms,
                        "is_surface": 1 if mean_sasa >= min_sasa else 0,
                    }
                )
        rows.sort(key=lambda row: (row["site"].split(":")[0], row["position"]))

        labels = {
            site_dim: {
                f"{row['site']}#{index}": index for index, row in enumerate(rows)
            },
            "statistic": {
                name: index
                for index, name in enumerate(
                    ("position", "mean_sasa", "n_atoms", "is_surface", "kind_code")
                )
            },
        }
        data = np.zeros((len(rows), 5), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = (
                row["position"],
                row["mean_sasa"],
                row["n_atoms"],
                row["is_surface"],
                1 if row["kind"] == "N-linked" else 2,
            )
        ctx[out_name] = Form(
            data=data,
            dims=[site_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_sites": len(rows),
                "n_exposed": int(sum(row["is_surface"] for row in rows)),
                "min_sasa": min_sasa,
                "include_o_linked": include_o_linked,
                "motifs": [row["motif"] for row in rows],
                "kinds": [row["kind"] for row in rows],
            },
        )
        self._export_data = {
            "n_sites": len(rows),
            "n_exposed": int(sum(row["is_surface"] for row in rows)),
            "sites": [row["site"] for row in rows],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
