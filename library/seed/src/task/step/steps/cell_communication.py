"""Ligand-receptor communication scores between cell clusters.

Inputs: a 2D expression matrix [cell, gene] and 2D cluster labels [cell, cluster].
The pairs table is a CSV with ``ligand`` and ``receptor`` columns. For every
ordered pair of distinct clusters the score is
``mean_ligand(cluster_a) * mean_receptor(cluster_b)``.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def _axis_labels(form: Form, dim: str, n: int):
    labels = (form.labels or {}).get(dim)
    if labels:
        return list(labels.keys())
    return [str(i) for i in range(n)]


def _cluster_ids(labels_form: Form, n: int):
    data = np.asarray(labels_form.data)
    if data.ndim == 2:
        if data.shape[1] != 1:
            raise ValueError("cluster labels must have exactly one column")
        data = data[:, 0]
    if data.ndim != 1 or data.size != n:
        raise ValueError("cluster labels must have one value per cell")
    ids = []
    for value in data:
        number = float(value)
        ids.append(str(int(round(number))) if number.is_integer() else f"{number:g}")
    return ids


def read_pairs(path: Path):
    if not path.is_file():
        raise ValueError(f"pairs table not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.reader(handle) if row and any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("pairs table is empty")
    header = [cell.strip().lower() for cell in rows[0]]
    ligand_key = next((name for name in ("ligand", "ligand_gene", "source") if name in header), None)
    receptor_key = next((name for name in ("receptor", "receptor_gene", "target") if name in header), None)
    if ligand_key and receptor_key:
        ligand_position = header.index(ligand_key)
        receptor_position = header.index(receptor_key)
        body = rows[1:]
    else:
        ligand_position, receptor_position = 0, 1
        body = rows
    pairs = []
    for row in body:
        if len(row) <= max(ligand_position, receptor_position):
            continue
        ligand = row[ligand_position].strip()
        receptor = row[receptor_position].strip()
        if ligand and receptor:
            pairs.append((ligand, receptor))
    if not pairs:
        raise ValueError("pairs table has no ligand/receptor rows")
    return pairs


def communication_scores(expression, genes, clusters, pairs, min_mean=0.1):
    x = np.asarray(expression, dtype=float)
    if x.ndim != 2:
        raise ValueError("expression must be 2D")
    if x.shape[1] != len(genes):
        raise ValueError("gene labels do not match the expression matrix")
    if x.shape[0] != len(clusters):
        raise ValueError("cluster labels do not match the number of cells")
    gene_index = {gene: position for position, gene in enumerate(genes)}
    names = sorted(set(clusters))
    means = {}
    for name in names:
        rows = np.array([cell for cell, value in enumerate(clusters) if value == name])
        means[name] = x[rows].mean(axis=0)

    usable = 0
    skipped = 0
    rows = []
    for ligand, receptor in pairs:
        ligand_position = gene_index.get(ligand)
        receptor_position = gene_index.get(receptor)
        if ligand_position is None or receptor_position is None:
            skipped += 1
            continue
        usable += 1
        for cluster_a in names:
            ligand_mean = float(means[cluster_a][ligand_position])
            if ligand_mean < min_mean:
                continue
            for cluster_b in names:
                if cluster_a == cluster_b:
                    continue
                score = ligand_mean * float(means[cluster_b][receptor_position])
                if score > 0.0:
                    rows.append((ligand, receptor, cluster_a, cluster_b, score))
    rows.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return rows, usable, skipped, names


class CellCommunicationStep(Step):
    """Ligand-receptor communication scores between clusters."""

    provider = "operon-core"
    parameters_file = "cell_communication.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "cell_communication",
        "version": "1.0.0",
        "kind": "operator",
        "title": "cell_communication",
        "description": "Ligand-receptor communication scores between cell clusters.",
        "category": "Omics",
        "icon": "MessagesSquare",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "gene"],
                },
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "cluster"],
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["interaction", "score"],
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
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        cells = genes = 0
        if inputs:
            data = getattr(inputs[0], "data", None)
            if data is not None and getattr(data, "ndim", 0) == 2:
                cells, genes = int(data.shape[0]), int(data.shape[1])
        return max(cells * genes * 8, 8 * 1024**2), max(genes * 8, 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) != 2:
            raise StepError("cell_communication requires expression and cluster labels")
        expression, labels_form = inputs
        if not isinstance(expression, Form) or not isinstance(labels_form, Form):
            raise StepError("cell_communication requires two Forms")
        if expression.data.ndim != 2:
            raise StepError("cell_communication requires a 2D expression matrix")
        params = dict(ctx.step_params)
        table = str(params.get("pairs_table") or "")
        if not table:
            raise StepError("cell_communication requires pairs_table")
        table_path = Path(table)
        if not table_path.is_absolute():
            table_path = Path(getattr(ctx, "task_dir", ".")) / table_path
        min_mean = float(params.get("min_mean") if params.get("min_mean") is not None else 0.1)
        out_name = params.get("output") or self.name
        genes = _axis_labels(expression, "gene", expression.data.shape[1])
        try:
            clusters = _cluster_ids(labels_form, expression.data.shape[0])
            pairs = read_pairs(table_path)
            rows, usable, skipped, names = communication_scores(
                expression.data, genes, clusters, pairs, min_mean
            )
        except ValueError as exc:
            raise StepError(f"cell_communication: {exc}") from exc

        interactions = [f"{ligand}^{receptor}|{a}|{b}" for ligand, receptor, a, b, _ in rows]
        values = np.asarray([[score] for *_, score in rows], dtype=float).reshape(-1, 1)
        labels = {
            "interaction": {name: index for index, name in enumerate(interactions)},
            "score": {"score": 0},
        }
        info = {
            "n_clusters": len(names),
            "n_pairs_usable": usable,
            "n_pairs_skipped": skipped,
            "min_mean": min_mean,
        }
        ctx[out_name] = Form(
            data=values,
            dims=["interaction", "score"],
            labels=labels,
            info=info,
        )
        self._export_data = {
            "n_interactions": len(interactions),
            "n_clusters": len(names),
            "n_pairs_usable": usable,
            "n_pairs_skipped": skipped,
            "max_score": float(values.max()) if values.size else 0.0,
        }
        print(
            f"[cell_communication] interactions={len(interactions)} clusters={len(names)} "
            f"pairs={usable}/{usable + skipped}"
        )

    def export(self, ctx):
        return self._export_data
