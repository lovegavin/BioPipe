"""Domain boundaries from the CA contact graph.

Two residues are in contact when their CA atoms are within ``contact_cutoff``
angstrom and at least ``min_separation`` positions apart.  Disconnected graphs
give their connected components directly; connected graphs are split with a
spectral clustering whose cluster count comes from the normalized-Laplacian
eigengap.  Residues whose contacts cross a domain border mark the boundary.
"""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps.structure_ss_bridge_network import ca_coordinates

_STATISTICS = ("domain", "cross_contacts", "is_boundary")


def ca_adjacency(coordinates: np.ndarray, *, cutoff: float = 8.0, min_separation: int = 3) -> np.ndarray:
    """Boolean contact matrix for CA coordinates."""

    count = len(coordinates)
    distances = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    separation = np.abs(np.arange(count)[:, None] - np.arange(count)[None, :])
    adjacency = (distances <= cutoff) & (separation >= min_separation)
    np.fill_diagonal(adjacency, False)
    return adjacency


def connected_components(adjacency: np.ndarray) -> list[list[int]]:
    """Connected components as index lists, in first-appearance order."""

    count = adjacency.shape[0]
    seen = np.zeros(count, dtype=bool)
    components: list[list[int]] = []
    for start in range(count):
        if seen[start]:
            continue
        stack = [start]
        seen[start] = True
        members: list[int] = []
        while stack:
            node = stack.pop()
            members.append(node)
            for neighbour in np.flatnonzero(adjacency[node]):
                if not seen[neighbour]:
                    seen[neighbour] = True
                    stack.append(int(neighbour))
        components.append(sorted(members))
    return components


def normalized_laplacian(adjacency: np.ndarray) -> np.ndarray:
    """Symmetric normalized Laplacian ``I - D^-1/2 A D^-1/2``."""

    adjacency = adjacency.astype(np.float64)
    degree = adjacency.sum(axis=1)
    inverse = np.zeros_like(degree)
    positive = degree > 0
    inverse[positive] = 1.0 / np.sqrt(degree[positive])
    laplacian = -adjacency * inverse[:, None] * inverse[None, :]
    laplacian[np.diag_indices_from(laplacian)] = 1.0
    return laplacian


def eigengap_domains(adjacency: np.ndarray, max_domains: int, min_gap_ratio: float) -> tuple[int, np.ndarray]:
    """Choose the domain count from the normalized-Laplacian eigengap."""

    eigenvalues = np.linalg.eigvalsh(normalized_laplacian(adjacency))
    count = len(eigenvalues)
    if count < 4:
        raise StepError("structure_domain_boundary: at least four residues are required")
    upper = min(max_domains, count - 2)
    if upper < 2:
        raise StepError("structure_domain_boundary: too few residues for a domain split")
    gaps = [float(eigenvalues[k] - eigenvalues[k - 1]) for k in range(2, upper + 1)]
    ordered = sorted(gaps, reverse=True)
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else 0.0
    if best <= 0.02 or (second > 0 and best < min_gap_ratio * second):
        raise StepError(
            "structure_domain_boundary: no clear domain boundary was detected "
            f"(largest eigengap {best:.4f}); pass n_domains explicitly"
        )
    domains = 2 + gaps.index(best)
    return domains, eigenvalues


def kmeans_embedding(embedding: np.ndarray, k: int, *, seed: int = 0, iterations: int = 100) -> np.ndarray:
    """Deterministic k-means++ over the spectral embedding rows."""

    rng = np.random.default_rng(seed)
    count = len(embedding)
    centres = [embedding[int(rng.integers(count))]]
    for _ in range(1, k):
        distances = np.min(
            np.linalg.norm(embedding[:, None, :] - np.asarray(centres)[None, :, :], axis=2), axis=1
        )
        probabilities = distances**2
        total = probabilities.sum()
        if total <= 0:
            centres.append(embedding[int(rng.integers(count))])
            continue
        centres.append(embedding[int(rng.choice(count, p=probabilities / total))])
    centres_array = np.asarray(centres, dtype=np.float64)
    labels = np.zeros(count, dtype=int)
    for _ in range(iterations):
        distances = np.linalg.norm(
            embedding[:, None, :] - centres_array[None, :, :], axis=2
        )
        updated = np.argmin(distances, axis=1)
        if np.array_equal(updated, labels) and _ > 0:
            break
        labels = updated
        for index in range(k):
            members = embedding[labels == index]
            if len(members):
                centres_array[index] = members.mean(axis=0)
    return labels


def spectral_domains(adjacency: np.ndarray, domains: int, *, seed: int = 0) -> np.ndarray:
    """Spectral clustering with ``domains`` clusters."""

    eigenvalues, eigenvectors = np.linalg.eigh(normalized_laplacian(adjacency))
    embedding = eigenvectors[:, :domains]
    norms = np.linalg.norm(embedding, axis=1)
    norms[norms == 0] = 1.0
    embedding = embedding / norms[:, None]
    labels = kmeans_embedding(embedding, domains, seed=seed)
    if len(set(labels.tolist())) != domains:
        raise StepError(
            "structure_domain_boundary: the spectral embedding does not separate the requested "
            f"{domains} domains"
        )
    return labels


def domain_assignment(
    adjacency: np.ndarray,
    *,
    n_domains: int = 0,
    max_domains: int = 4,
    min_gap_ratio: float = 1.5,
    seed: int = 0,
) -> tuple[np.ndarray, str]:
    """Label every residue with a domain index and report how it was chosen."""

    components = connected_components(adjacency)
    if n_domains > 0:
        if n_domains > len(adjacency) // 2:
            raise StepError(
                f"structure_domain_boundary: {n_domains} domains are too many for "
                f"{len(adjacency)} residues"
            )
        return spectral_domains(adjacency, n_domains, seed=seed), "spectral"
    if len(components) > 1:
        labels = np.full(len(adjacency), -1, dtype=int)
        for index, component in enumerate(sorted(components, key=lambda item: item[0])):
            labels[component] = index
        return labels, "components"
    domains, _eigenvalues = eigengap_domains(adjacency, max_domains, min_gap_ratio)
    return spectral_domains(adjacency, domains, seed=seed), "spectral"


def boundary_rows(
    adjacency: np.ndarray, domains: np.ndarray, labels: list[str]
) -> list[tuple[str, int, int, int]]:
    """Per-residue domain, cross-domain contact count and boundary flag."""

    rows: list[tuple[str, int, int, int]] = []
    for index, label in enumerate(labels):
        crossing = int(
            np.sum(adjacency[index] & (domains != domains[index]))
        )
        rows.append((label, int(domains[index]), crossing, 1 if crossing else 0))
    return rows


class StructureDomainBoundaryStep(Step):
    """Split a CA contact graph into domains and flag the boundary residues."""

    provider = "operon-core"

    parameters_file = "structure_domain_boundary.StructureDomainBoundaryStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_domain_boundary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Structure domain boundary",
        "description": (
            "Segment a chain into domains from the CA contact graph (connected components or "
            "normalized-Laplacian spectral clustering) and report each residue's domain, the "
            "number of cross-domain contacts and whether it sits on a domain boundary."
        ),
        "category": "Structure",
        "icon": "ShareNetwork",
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
        form = inputs[0]
        atom_dim = str(params.get("atom_dim") or "atom")
        field_dim = str(params.get("field_dim") or "field")
        residue_dim = str(params.get("residue_dim") or "residue")
        cutoff = float(params.get("contact_cutoff") if params.get("contact_cutoff") is not None else 8.0)
        separation = int(params.get("min_separation") if params.get("min_separation") is not None else 3)
        n_domains = int(params.get("n_domains") if params.get("n_domains") is not None else 0)
        max_domains = int(params.get("max_domains") if params.get("max_domains") is not None else 4)
        min_gap_ratio = float(
            params.get("min_gap_ratio") if params.get("min_gap_ratio") is not None else 1.5
        )
        seed = int(params.get("seed") if params.get("seed") is not None else 0)
        out_name = str(params.get("output") or "domains")

        if not 4.0 <= cutoff <= 15.0:
            raise StepError("structure_domain_boundary: contact_cutoff must be between 4 and 15 angstrom")
        if separation < 1:
            raise StepError("structure_domain_boundary: min_separation must be at least 1")
        if not 0 <= n_domains <= 8:
            raise StepError("structure_domain_boundary: n_domains must be between 0 and 8")
        if not 2 <= max_domains <= 8:
            raise StepError("structure_domain_boundary: max_domains must be between 2 and 8")
        if min_gap_ratio < 1.0:
            raise StepError("structure_domain_boundary: min_gap_ratio must be at least 1")

        labels, coordinates = ca_coordinates(form, atom_dim, field_dim)
        adjacency = ca_adjacency(coordinates, cutoff=cutoff, min_separation=separation)
        if not adjacency.any():
            raise StepError(
                "structure_domain_boundary: the CA contact graph has no edges; relax "
                "contact_cutoff or min_separation"
            )
        domains, method = domain_assignment(
            adjacency,
            n_domains=n_domains,
            max_domains=max_domains,
            min_gap_ratio=min_gap_ratio,
            seed=seed,
        )
        rows = boundary_rows(adjacency, domains, labels)
        boundary = [row[0] for row in rows if row[3]]
        data = np.asarray(
            [[row[1], row[2], row[3]] for row in rows], dtype=np.float32
        ).reshape(len(rows), 3)
        out = Form(
            data=data,
            dims=[residue_dim, "statistic"],
            labels={
                residue_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "n_domains": int(len(set(domains.tolist()))),
                "domain_sizes": {
                    str(int(index)): int(np.sum(domains == index))
                    for index in range(int(domains.max()) + 1)
                },
                "boundary_residues": boundary,
                "n_boundary_residues": len(boundary),
                "method": method,
                "contact_cutoff": cutoff,
                "min_separation": separation,
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_domains": out.info["n_domains"],
            "n_boundary_residues": len(boundary),
            "method": method,
        }
        print(
            f"[structure_domain_boundary] {out.info['n_domains']} domains ({method}), "
            f"{len(boundary)} boundary residues"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
