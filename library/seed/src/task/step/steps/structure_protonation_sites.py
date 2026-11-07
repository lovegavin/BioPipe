"""Per-residue pKa estimates from a structure."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._protein_common import column_index, decode_column

_BASE_PKA = {"ASP": 3.9, "GLU": 4.3, "HIS": 6.0, "CYS": 8.3, "TYR": 10.1, "LYS": 10.5, "ARG": 12.5}
_ACIDIC = frozenset({"ASP", "GLU", "CYS", "TYR"})
_BASIC = frozenset({"HIS", "LYS", "ARG"})


def protonation_fraction(pka: float, ph: float, *, acidic: bool) -> float:
    if acidic:
        return float(1.0 / (1.0 + 10.0 ** (pka - ph)))
    return float(1.0 / (1.0 + 10.0 ** (ph - pka)))


def pka_shift(residue: str, neighbours: list[str], *, shift: float = 0.4) -> float:
    total = 0.0
    for neighbour in neighbours:
        if neighbour in _ACIDIC and residue in _BASIC:
            total -= shift
        elif neighbour in _BASIC and residue in _ACIDIC:
            total += shift
    return float(_BASE_PKA[residue] + total)


def titratable_rows(groups: list[dict], *, ph: float, cutoff: float = 6.0, shift: float = 0.4) -> list[dict]:
    """Build rows for every titratable residue; groups carry coordinates."""

    rows = []
    for group in groups:
        residue = group["residue"]
        if residue not in _BASE_PKA:
            continue
        neighbours = []
        for other in groups:
            if other is group or other["residue"] not in _BASE_PKA:
                continue
            distance = float(np.linalg.norm(np.asarray(group["coords"]) - np.asarray(other["coords"])))
            if distance <= cutoff:
                neighbours.append(other["residue"])
        pka = pka_shift(residue, neighbours, shift=shift)
        fraction = protonation_fraction(pka, ph, acidic=residue in _ACIDIC)
        rows.append(
            {
                "label": group["label"],
                "residue": residue,
                "pka": pka,
                "fraction_charged": fraction,
                "n_neighbours": len(neighbours),
                "charged_state": 1.0 if fraction >= 0.5 else 0.0,
            }
        )
    if not rows:
        raise StepError("structure_protonation_sites: the structure carries no titratable residue")
    return rows


def residue_groups(form: Form, atom_dim: str, field_dim: str) -> list[dict]:
    labels = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    numbers = np.asarray(form.data, dtype=np.float64)[:, column_index(form, field_dim, "residue_number")].astype(int)
    coords = np.asarray(form.data, dtype=np.float64)[:, [column_index(form, field_dim, "x"), column_index(form, field_dim, "y"), column_index(form, field_dim, "z")]]
    seen: dict[str, dict] = {}
    for index, (residue, chain, number) in enumerate(zip(labels, chains, numbers)):
        key = f"{chain}:{residue}:{number}"
        entry = seen.setdefault(key, {"label": key, "residue": residue, "coords": [], "n": 0})
        entry["coords"].append(coords[index])
        entry["n"] += 1
    groups = []
    for entry in seen.values():
        groups.append({"label": entry["label"], "residue": entry["residue"], "coords": np.asarray(entry["coords"]).mean(axis=0)})
    if not groups:
        raise StepError("structure_protonation_sites: the structure form is empty")
    return groups


class StructureProtonationSitesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_protonation_sites.StructureProtonationSitesStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_protonation_sites",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Protonation sites",
        "category": "Structure",
        "icon": "Waves",
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
        groups = residue_groups(inputs[0], params["atom_dim"], params["field_dim"])
        rows = titratable_rows(groups, ph=float(params.get("ph", 7.4)), cutoff=float(params.get("cutoff", 6.0)), shift=float(params.get("shift", 0.4)))
        data = np.array([[r["pka"], r["fraction_charged"], r["n_neighbours"]] for r in rows], dtype=np.float32)
        ctx[params.get("output", "sites")] = Form(
            data=data,
            dims=["residue", "statistic"],
            labels={"residue": {r["label"]: i for i, r in enumerate(rows)}, "statistic": {"pka": 0, "fraction_charged": 1, "n_neighbours": 2}},
            info={"missing_code": np.nan, "ph": float(params.get("ph", 7.4)), "n_sites": len(rows), "n_titratable": sum(1 for r in rows if r["pka"]), "cutoff": float(params.get("cutoff", 6.0)), "net_charge": float(sum(r["fraction_charged"] * (1 if r["residue"] in _BASIC else -1) for r in rows))},
        )
        self._export_data = {"n_sites": len(rows), "ph": float(params.get("ph", 7.4))}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
