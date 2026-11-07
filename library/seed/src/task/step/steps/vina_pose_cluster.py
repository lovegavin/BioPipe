"""Cluster docked poses by symmetry-aware heavy-atom RMSD."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps.structure_ligand_pose_rmsd import symmetry_rmsd


def _columns(form: Form, field_dim: str) -> dict[str, int]:
    labels = form.labels[field_dim]
    return {str(name): int(position) for name, position in labels.items()}


def pose_tables(form: Form, pose_dim: str, atom_dim: str, field_dim: str):
    """Coordinates and per-atom element codes for every pose."""

    for dim in (pose_dim, atom_dim, field_dim):
        if dim not in form.dims:
            raise StepError(f"vina_pose_cluster: the input has no '{dim}' dimension")
    if form.dims != [pose_dim, atom_dim, field_dim]:
        raise StepError(
            f"vina_pose_cluster: expected dims [{pose_dim}, {atom_dim}, {field_dim}], "
            f"got {form.dims}"
        )
    columns = _columns(form, field_dim)
    for name in ("x", "y", "z"):
        if name not in columns:
            raise StepError(f"vina_pose_cluster: the input has no '{name}' column")
    coordinates_column = "atomic_number" if "atomic_number" in columns else None
    label_order = sorted(form.labels[pose_dim].items(), key=lambda item: item[1])
    tables = []
    for label, position in label_order:
        block = np.asarray(form.data[position], dtype=np.float64)
        coordinates = np.stack(
            [block[:, columns["x"]], block[:, columns["y"]], block[:, columns["z"]]], axis=1
        )
        if coordinates_column is not None:
            elements = block[:, columns[coordinates_column]].astype(int).tolist()
        else:
            elements = ["C"] * coordinates.shape[0]
        tables.append(
            {
                "label": str(label),
                "coordinates": coordinates,
                "elements": elements,
                "n_atoms": int(coordinates.shape[0]),
            }
        )
    if not tables:
        raise StepError("vina_pose_cluster: the pose form is empty")
    return tables


def cluster_tables(
    tables: list[dict],
    *,
    cutoff: float = 2.0,
    allow_symmetry: bool = True,
) -> tuple[list[dict], int]:
    """Greedy leader clustering; the first pose of a cluster is its representative."""

    if cutoff <= 0:
        raise StepError("vina_pose_cluster: cutoff must be positive")
    representatives: list[int] = []
    rows: list[dict] = []
    for index, table in enumerate(tables):
        assigned = None
        for cluster, representative in enumerate(representatives):
            reference = tables[representative]
            if reference["n_atoms"] != table["n_atoms"]:
                continue
            value = symmetry_rmsd(
                table["coordinates"],
                reference["coordinates"],
                table["elements"],
                allow_symmetry=allow_symmetry,
            )[0]
            if value <= cutoff:
                assigned = cluster
                break
        if assigned is None:
            representatives.append(index)
            assigned = len(representatives) - 1
        rows.append(
            {
                "pose": table["label"],
                "cluster": assigned + 1,
                "n_atoms": table["n_atoms"],
                "distance": 0.0
                if representatives[assigned] == index
                else float(
                    symmetry_rmsd(
                        table["coordinates"],
                        tables[representatives[assigned]]["coordinates"],
                        table["elements"],
                        allow_symmetry=allow_symmetry,
                    )[0]
                ),
            }
        )
    return rows, len(representatives)


class VinaPoseClusterStep(Step):
    """Group docked poses into binding modes."""

    provider = "operon-core"

    parameters_file = "vina_pose_cluster.VinaPoseClusterStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vina_pose_cluster",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Docking pose clustering",
        "description": (
            "Cluster the poses returned by vina_dock with symmetry-aware heavy-atom "
            "RMSD and greedy leader clustering, reporting the cluster of every pose "
            "and the distance to its cluster representative."
        ),
        "category": "Machine Learning",
        "icon": "CirclesThree",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "pose_dim"}, {"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 3,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        (poses,) = inputs
        pose_dim = str(params.get("pose_dim") or "pose")
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        out_name = str(params.get("output") or "clusters")
        cutoff = float(params.get("cutoff") or 2.0)
        allow_symmetry = bool(params.get("allow_symmetry", True))

        tables = pose_tables(poses, pose_dim, atom_dim, field_dim)
        rows, n_clusters = cluster_tables(tables, cutoff=cutoff, allow_symmetry=allow_symmetry)
        data = np.asarray(
            [[row["cluster"], row["n_atoms"], row["distance"]] for row in rows],
            dtype=np.float32,
        )
        labels = {
            "pose": {row["pose"]: index for index, row in enumerate(rows)},
            "statistic": {"cluster": 0, "n_atoms": 1, "distance": 2},
        }
        sizes = [sum(1 for row in rows if row["cluster"] == cluster) for cluster in range(1, n_clusters + 1)]
        form = Form(
            data,
            dims=["pose", "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_poses": len(rows),
                "n_clusters": n_clusters,
                "cluster_sizes": sizes,
                "representatives": [
                    next(row["pose"] for row in rows if row["cluster"] == cluster)
                    for cluster in range(1, n_clusters + 1)
                ],
                "cutoff": cutoff,
                "allow_symmetry": allow_symmetry,
            },
        )
        ctx[out_name] = form
        self._export_data = form

    def export(self, ctx) -> dict:
        form = self._export_data
        return {
            "operator": "vina_pose_cluster",
            "n_poses": int(form.info["n_poses"]),
            "n_clusters": int(form.info["n_clusters"]),
        }
