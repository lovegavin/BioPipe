"""ProteinMPNN interface cutoff scan."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from pathlib import Path

from src.task.step.steps.proteinmpnn_hotspot_masked_design import hotspot_mask
from src.task.step.steps.proteinmpnn_masked_design import (
    mask_payload,
    parse_design_fasta,
    pdb_chains,
    run_masked_designer,
)
from src.task.step.steps._protein_common import column_index, contact_stats, decode_column
from src.task.step.steps._structure_common import pick_chain_sides

_REQUIRED = ("x", "y", "z", "chain", "resname", "residue_number")


def parse_cutoffs(text: str) -> list[float]:
    values = []
    for token in str(text or "").replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError:
            raise StepError(
                f"proteinmpnn_interface_scan: cutoff '{token}' is not a number"
            ) from None
        if value <= 0:
            raise StepError("proteinmpnn_interface_scan: cutoffs must be positive")
        if value not in values:
            values.append(value)
    if not values:
        raise StepError("proteinmpnn_interface_scan: cutoffs must list at least one value")
    return values


class ProteinmpnnInterfaceScanStep(Step):
    provider = "operon-core"
    parameters_file = "proteinmpnn_interface_scan.ProteinmpnnInterfaceScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_interface_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN interface scan",
        "category": "Machine Learning",
        "icon": "ChartLine",
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
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False},
            },
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        field_dim = params["field_dim"]
        for name in _REQUIRED:
            if name not in dict(form.labels[field_dim]):
                raise StepError(
                    f"proteinmpnn_interface_scan: the structure form has no '{name}' column"
                )
        structure = Path(str(params["structure_path"])).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_interface_scan: structure_path {structure} is not a file")
        chains = pdb_chains(structure)
        sides = pick_chain_sides(set(chains), params.get("binder_chains", ""), params.get("target_chains", ""), "proteinmpnn_interface_scan")
        binder_chains, target_chains = sides
        binder_sel = np.isin(decode_column(form, field_dim, "chain"), binder_chains)
        target_sel = np.isin(decode_column(form, field_dim, "chain"), target_chains)
        columns = [column_index(form, field_dim, name) for name in ("x", "y", "z", "residue_number")]
        coords = np.asarray(form.data, dtype=np.float64)[:, columns[:3]]
        numbers = np.asarray(form.data, dtype=np.float64)[:, columns[3]].astype(int)
        chain_values = decode_column(form, field_dim, "chain")
        resname_values = decode_column(form, field_dim, "resname")

        rows = []
        cutoffs = parse_cutoffs(params.get("cutoffs", "4.0,4.5,5.0"))
        for cutoff in cutoffs:
            counts, distances = contact_stats(coords[binder_sel], coords[target_sel], cutoff)
            labels = np.array(
                [
                    f"{chain}:{res}:{int(number)}"
                    for chain, res, number in zip(chain_values, resname_values, numbers)
                ]
            )
            binder_labels = labels[binder_sel]
            binder_mask = hotspot_mask_list(
                binder_labels, counts, distances, cutoff, int(params.get("min_contacts", 1)), int(params.get("top_n", 0))
            )
            payload = mask_payload(binder_mask, chains, structure.stem)
            designs = run_masked_designer(params, structure, " ".join(binder_chains), payload)
            scores = np.array([float(d["score"]) for d in designs], dtype=np.float64)
            rows.append(
                {
                    "cutoff": cutoff,
                    "n_hotspots": int(sum(len(v) for v in binder_mask.values())),
                    "n_designs": len(designs),
                    "mean_score": float(scores.mean()),
                    "min_score": float(scores.min()),
                    "mean_global_score": float(np.mean([float(d["global_score"]) for d in designs])),
                }
            )
        data = np.array([[r["n_hotspots"], r["n_designs"], r["mean_score"], r["min_score"], r["mean_global_score"]] for r in rows], dtype=np.float32)
        labels = {f"cutoff{r['cutoff']:g}": index for index, r in enumerate(rows)}
        ctx[params.get("output", "scan")] = Form(
            data=data,
            dims=["cutoff", "statistic"],
            labels={"cutoff": labels, "statistic": {"n_hotspots": 0, "n_designs": 1, "mean_score": 2, "min_score": 3, "mean_global_score": 4}},
            info={"missing_code": np.nan, "cutoffs": [float(c) for c in cutoffs], "n_cutoffs": len(rows)},
        )
        self._export_data = {"n_cutoffs": len(rows), "cutoffs": [float(c) for c in cutoffs]}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))


def hotspot_mask_list(labels, counts, distances, cutoff, min_contacts, top_n):
    """Pick hotspot residues and return them keyed by chain."""

    mask: dict[str, list[int]] = {}
    order = np.argsort(-counts)
    selected = 0
    for index in order:
        if counts[index] < min_contacts:
            continue
        label = str(labels[index])
        chain, _res, number = label.split(":")
        mask.setdefault(chain, []).append(int(number))
        selected += 1
        if top_n and selected >= top_n:
            break
    if not mask:
        raise StepError(
            f"proteinmpnn_interface_scan: no binder residue reaches min_contacts at cutoff {cutoff:g}"
        )
    return {chain: sorted(set(values)) for chain, values in sorted(mask.items())}
