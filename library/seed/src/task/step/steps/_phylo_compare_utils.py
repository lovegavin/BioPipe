"""Shared helpers for phylogenetic comparative methods.

All three operators take a tree table (node x field) and a trait table
(sample x statistic). The tree table is the same representation produced by
``phylo_neighbor_joining`` and the Newick reader: encoded ``parent``,
``branch_length``, ``depth`` and ``is_leaf`` fields.
"""
from __future__ import annotations

import math

import numpy as np

from src.core import StepError
from src.task.step.steps._phylo_common import load_tree


def load_comparative(tree_form, trait_form, node_dim, field_dim, sample_dim,
                     statistic_dim, value_field, operator):
    """Return (tree, tip_values) after aligning trait samples with tree tips."""
    tree = load_tree(tree_form, node_dim=node_dim, field_dim=field_dim)
    if trait_form.data.ndim != 2:
        raise StepError(f"{operator}: trait table must be 2-D")
    if sample_dim not in trait_form.dims or statistic_dim not in trait_form.dims:
        raise StepError(
            f"{operator}: trait table is missing dims {sample_dim!r} or {statistic_dim!r}"
        )
    sample_labels = trait_form.labels.get(sample_dim) or {}
    field_labels = trait_form.labels.get(statistic_dim) or {}
    if value_field not in field_labels:
        raise StepError(f"{operator}: trait table has no {value_field!r} column")
    column = int(field_labels[value_field])
    positions = {str(name): int(index) for name, index in sample_labels.items()}
    data = np.asarray(trait_form.data, dtype=np.float64)
    tip_names = [tree.names[index] for index in tree.tips]
    missing = [name for name in tip_names if name not in positions]
    if missing:
        preview = ", ".join(missing[:3])
        raise StepError(f"{operator}: traits are missing for {len(missing)} tip(s): {preview}")
    values = np.array([data[positions[name], column] for name in tip_names], dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise StepError(f"{operator}: trait values must be finite")
    extra = set(positions) - set(tip_names)
    if extra:
        raise StepError(f"{operator}: {len(extra)} trait sample(s) are not tree tips")
    return tree, values


def _depths(tree) -> np.ndarray:
    depth = np.zeros(len(tree.names), dtype=np.float64)
    for node in tree.postorder()[::-1]:
        for child in tree.children[node]:
            depth[child] = depth[node] + float(tree.length[child])
    return depth


def _ancestors(tree) -> list[list[int]]:
    chains: list[list[int]] = [[] for _ in range(len(tree.names))]
    order = tree.postorder()[::-1]
    for node in order:
        if node == tree.root:
            chains[node] = [node]
        else:
            chains[node] = chains[int(tree.parent[node])] + [node]
    return chains


def _lca_distance(tree, chains, depth, a, b) -> float:
    set_b = set(chains[b])
    for node in reversed(chains[a]):
        if node in set_b:
            return float(depth[node])
    raise StepError("phylo: tree is disconnected")


def tip_covariance(tree) -> np.ndarray:
    """Brownian-motion covariance matrix of the tips (root-to-tip distances)."""
    depth = _depths(tree)
    chains = _ancestors(tree)
    tips = tree.tips
    n = len(tips)
    matrix = np.empty((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i, n):
            value = _lca_distance(tree, chains, depth, tips[i], tips[j])
            matrix[i, j] = value
            matrix[j, i] = value
    if np.any(np.diag(matrix) <= 0):
        raise StepError("phylo: every tip needs a positive root-to-tip distance")
    return matrix


def node_covariance(tree) -> tuple[np.ndarray, np.ndarray]:
    """Return (cov(node, tip), var(node)) matrices for all nodes."""
    depth = _depths(tree)
    chains = _ancestors(tree)
    tips = tree.tips
    internal = [node for node in range(len(tree.names)) if tree.children[node]]
    cov = np.empty((len(internal), len(tips)), dtype=np.float64)
    for row, node in enumerate(internal):
        for col, tip in enumerate(tips):
            cov[row, col] = _lca_distance(tree, chains, depth, node, tip)
    var = np.array([depth[node] for node in internal], dtype=np.float64)
    return cov, var


def felsenstein_contrasts(tree, values: np.ndarray) -> tuple[list[int], np.ndarray, np.ndarray]:
    """Return (internal nodes, standardized contrast, contrast variance)."""
    n = len(tree.names)
    x = np.zeros(n, dtype=np.float64)
    var = np.zeros(n, dtype=np.float64)
    for index, tip in enumerate(tree.tips):
        x[tip] = values[index]
    nodes: list[int] = []
    contrasts: list[float] = []
    variances: list[float] = []
    for node in tree.postorder():
        children = tree.children[node]
        if not children:
            continue
        if len(children) != 2:
            raise StepError(
                "phylo_contrasts: independent contrasts require a fully binary tree"
            )
        c1, c2 = children
        v1 = var[c1] + float(tree.length[c1])
        v2 = var[c2] + float(tree.length[c2])
        if v1 <= 0 or v2 <= 0:
            raise StepError("phylo_contrasts: branch lengths must be positive")
        contrasts.append((x[c1] - x[c2]) / math.sqrt(v1 + v2))
        variances.append(v1 + v2)
        nodes.append(node)
        x[node] = (x[c1] / v1 + x[c2] / v2) / (1.0 / v1 + 1.0 / v2)
        var[node] = v1 * v2 / (v1 + v2)
    # The root contrast is not an independent contrast.
    return nodes, np.array(contrasts), np.array(variances)


def reml_ancestral(cov: np.ndarray, values: np.ndarray):
    """GLS/REML estimate of the root mean and of every internal node."""
    n = cov.shape[0]
    inverse = np.linalg.inv(cov)
    ones = np.ones(n, dtype=np.float64)
    denominator = float(ones @ inverse @ ones)
    if denominator <= 0:
        raise StepError("phylo_ancestral: covariance matrix is singular")
    mean = float(ones @ inverse @ values) / denominator
    residual = values - mean
    return mean, inverse, residual


def lambda_loglik(cov: np.ndarray, values: np.ndarray, lam: float) -> float:
    """Gaussian BM log-likelihood with Pagel's lambda applied to off-diagonals."""
    n = cov.shape[0]
    transformed = cov.copy()
    off = ~np.eye(n, dtype=bool)
    transformed[off] *= lam
    sign, logdet = np.linalg.slogdet(transformed)
    if sign <= 0:
        return -math.inf
    inverse = np.linalg.inv(transformed)
    ones = np.ones(n, dtype=np.float64)
    denominator = float(ones @ inverse @ ones)
    if denominator <= 0:
        return -math.inf
    mean = float(ones @ inverse @ values) / denominator
    residual = values - mean
    sigma2 = float(residual @ inverse @ residual) / n
    if sigma2 <= 0:
        return -math.inf
    return -0.5 * (n * math.log(2.0 * math.pi * sigma2) + logdet + n)
