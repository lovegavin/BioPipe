"""ProteinMPNN interface redesign temperature scan."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from pathlib import Path

from src.task.step.steps._protein_common import contact_stats, decode_column
from src.task.step.steps._structure_common import pick_chain_sides
from src.task.step.steps.proteinmpnn_hotspot_masked_design import hotspot_mask, hotspot_table
from src.task.step.steps.proteinmpnn_masked_design import (
    mask_payload,
    parse_design_fasta,
    pdb_chains,
    run_masked_designer,
)


def parse_temperatures(text: str) -> list[float]:
    values = []
    for token in str(text or "").replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError:
            raise StepError(f"proteinmpnn_interface_temperature_scan: temperature '{token}' is not a number") from None
        if value <= 0 or value > 1.0:
            raise StepError("proteinmpnn_interface_temperature_scan: temperatures must be in (0, 1]")
        if value not in values:
            values.append(value)
    if not values:
        raise StepError("proteinmpnn_interface_temperature_scan: temperatures must list at least one value")
    return values


def scan_rows(records: list[dict], temperature: float) -> dict:
    if not records:
        raise StepError(f"proteinmpnn_interface_temperature_scan: no design was generated at temperature {temperature:g}")
    scores = np.array([float(record["score"]) for record in records], dtype=np.float64)
    recovery = np.array([float(record.get("seq_recovery", 0.0)) for record in records], dtype=np.float64)
    return {
        "temperature": temperature,
        "n_designs": len(records),
        "mean_score": float(scores.mean()),
        "min_score": float(scores.min()),
        "mean_recovery": float(recovery.mean()),
        "max_recovery": float(recovery.max()),
    }


class ProteinmpnnInterfaceTemperatureScanStep(Step):
    provider = "operon-core"
    parameters_file = "proteinmpnn_interface_temperature_scan.ProteinmpnnInterfaceTemperatureScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_interface_temperature_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface temperature scan",
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "atom_dim"}, {"param": "field_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
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
        structure = Path(str(params["structure_path"])).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_interface_temperature_scan: structure_path {structure} is not a file")
        chains = pdb_chains(structure)
        binder_chains, target_chains = pick_chain_sides(set(chains), params.get("binder_chains", ""), params.get("target_chains", ""), "proteinmpnn_interface_temperature_scan")
        chain_values = decode_column(form, field_dim, "chain")
        numbers = np.asarray(form.data, dtype=np.float64)[:, 3].astype(int)
        coords = np.asarray(form.data, dtype=np.float64)[:, [0, 1, 2]]
        binder_sel = np.isin(chain_values, binder_chains)
        target_sel = np.isin(chain_values, target_chains)
        counts, distances = contact_stats(coords[binder_sel], coords[target_sel], float(params.get("cutoff", 4.5)))
        labels = np.array([f"{c}:{r}:{n}" for c, r, n in zip(chain_values, decode_column(form, field_dim, "resname"), numbers)])
        table = hotspot_table(labels[binder_sel], chain_values[binder_sel], numbers[binder_sel], binder_chains, counts, distances, min_contacts=int(params.get("min_contacts", 1)))
        mask = hotspot_mask(table, int(params.get("top_n", 0)))
        payload = mask_payload(mask, chains, structure.stem)
        rows = []
        for temperature in parse_temperatures(params.get("temperatures", "0.1,0.2,0.3")):
            step_params = dict(params)
            step_params["sampling_temp"] = f"{temperature:g}"
            rows.append(scan_rows(run_masked_designer(step_params, structure, " ".join(binder_chains), payload), temperature))
        data = np.array([[r["n_designs"], r["mean_score"], r["min_score"], r["mean_recovery"], r["max_recovery"]] for r in rows], dtype=np.float32)
        ctx[params.get("output", "scan")] = Form(
            data=data,
            dims=["temperature", "statistic"],
            labels={"temperature": {f"T{r['temperature']:g}": i for i, r in enumerate(rows)}, "statistic": {"n_designs": 0, "mean_score": 1, "min_score": 2, "mean_recovery": 3, "max_recovery": 4}},
            info={"missing_code": np.nan, "temperatures": [r["temperature"] for r in rows], "n_hotspots": int(sum(len(v) for v in mask.values())), "binder_chains": binder_chains},
        )
        self._export_data = {"n_temperatures": len(rows), "temperatures": [r["temperature"] for r in rows]}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
