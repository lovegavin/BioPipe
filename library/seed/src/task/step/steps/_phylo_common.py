"""Shared tree helpers for phylogeny-aware operators.

A tree reaches an operator as the node x field table produced by the
tree readers (``NewickReader``, ``PhyloXmlReader``): one row per node
with ``parent`` (encoded), ``branch_length``, ``depth`` and ``is_leaf``
columns. These helpers rebuild the parent/child structure once and
then provide the abundance propagation used by Faith's PD and the
UniFrac distances.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.core import StepError
from src.task.step.steps._ext_common import labels_in_order, reorder


@dataclass
class Tree:
    names: list[str]
    parent: np.ndarray
    length: np.ndarray
    children: list[list[int]]
    root: int
    tips: list[int]

    def postorder(self) -> list[int]:
        """Nodes with every child before its parent."""
        order: list[int] = []
        stack = [(self.root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            stack.append((node, True))
            for child in reversed(self.children[node]):
                stack.append((child, False))
        return order


def load_tree(form, node_dim: str = "node", field_dim: str = "field", label: str = "tree") -> Tree:
    """Validate a tree table and return its parent/child structure."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2-D tree table, got {form.data.ndim} dims")
    if node_dim not in form.dims or field_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {node_dim!r} and {field_dim!r}, got {list(form.dims)}"
        )
    node_labels = form.labels.get(node_dim) or {}
    field_labels = form.labels.get(field_dim) or {}
    if not node_labels:
        raise StepError(f"{label}: tree has no node labels")
    n = len(node_labels)
    names: list[str | None] = [None] * n
    for name, position in node_labels.items():
        position = int(position)
        if position < 0 or position >= n or names[position] is not None:
            raise StepError(f"{label}: node labels are not a contiguous 0..{n - 1} mapping")
        names[position] = str(name)
    fields = {str(key): int(value) for key, value in field_labels.items()}
    for required in ("parent", "branch_length", "is_leaf"):
        if required not in fields:
            raise StepError(f"{label}: tree table is missing the {required!r} field")

    data = reorder(form, node_dim, field_dim).astype(np.float64)
    encoders = form.info.get("encoders") or {}
    parent_encoder = (encoders.get(field_dim) or {}).get("parent")
    if parent_encoder is None or not hasattr(parent_encoder, "inverse_transform"):
        raise StepError(f"{label}: tree table has no encoded parent column")
    codes = data[:, fields["parent"]]
    if not np.all(np.isfinite(codes)):
        raise StepError(f"{label}: parent codes contain missing values")
    decoded = parent_encoder.inverse_transform(np.rint(codes).astype(np.int64))
    parent_names = [None if value is None else str(value) for value in decoded]

    positions = {name: index for index, name in enumerate(names)}
    parent = np.full(n, -1, dtype=np.int64)
    for index, parent_name in enumerate(parent_names):
        if parent_name is None or parent_name in ("None", "null", ""):
            continue
        if parent_name not in positions:
            raise StepError(
                f"{label}: parent {parent_name!r} of {names[index]!r} is not a node in this tree"
            )
        parent[index] = positions[parent_name]
        if parent[index] == index:
            raise StepError(f"{label}: node {names[index]!r} is its own parent")
    roots = np.flatnonzero(parent < 0)
    if roots.size != 1:
        raise StepError(f"{label}: expected exactly one root, found {int(roots.size)}")
    root = int(roots[0])

    lengths = data[:, fields["branch_length"]]
    flags = data[:, fields["is_leaf"]]
    if not np.all(np.isfinite(flags)):
        raise StepError(f"{label}: is_leaf column contains missing values")
    children: list[list[int]] = [[] for _ in range(n)]
    for index in range(n):
        if parent[index] >= 0:
            children[int(parent[index])].append(index)
    length = np.zeros(n, dtype=np.float64)
    for index in range(n):
        value = lengths[index]
        if index == root:
            if np.isfinite(value) and value != 0.0:
                raise StepError(f"{label}: the root must not carry a branch length")
            continue
        if not np.isfinite(value):
            raise StepError(f"{label}: node {names[index]!r} has no branch length")
        if value < 0:
            raise StepError(f"{label}: node {names[index]!r} has a negative branch length")
        length[index] = float(value)
    for index in range(n):
        marked = flags[index] > 0.5
        if marked != (not children[index]):
            raise StepError(f"{label}: is_leaf flag is inconsistent for {names[index]!r}")

    tree = Tree(
        names=[str(name) for name in names],
        parent=parent,
        length=length,
        children=children,
        root=root,
        tips=[index for index in range(n) if not children[index]],
    )
    if len(tree.postorder()) != n:
        raise StepError(f"{label}: the tree is not one connected rooted structure")
    return tree


def abundance_matrix(form, sample_dim: str, taxon_dim: str, label: str = "abundance"):
    """Return (matrix [sample, taxon] float64, sample labels, taxon labels)."""
    if form.data.ndim != 2:
        raise StepError(f"{label}: expected a 2-D abundance table, got {form.data.ndim} dims")
    if sample_dim not in form.dims or taxon_dim not in form.dims:
        raise StepError(
            f"{label}: expected dims {sample_dim!r} and {taxon_dim!r}, got {list(form.dims)}"
        )
    data = reorder(form, sample_dim, taxon_dim).astype(np.float64)
    missing = form.info.get("missing_code", np.nan)
    if isinstance(missing, float) and np.isnan(missing):
        absent = np.isnan(data)
    else:
        absent = data == missing
    data = np.where(absent, 0.0, data)
    if not np.all(np.isfinite(data)):
        raise StepError(f"{label}: abundances are not finite even after filling missing values")
    if np.any(data < 0):
        raise StepError(f"{label}: abundances must be non-negative")
    return data, labels_in_order(form, sample_dim), labels_in_order(form, taxon_dim)


def node_counts(counts: np.ndarray, taxa: list[str], tree: Tree, label: str = "tree") -> np.ndarray:
    """Propagate tip abundances to every node, as scikit-bio does."""
    tips = {tree.names[index]: index for index in tree.tips}
    missing = [str(name) for name in taxa if str(name) not in tips]
    if missing:
        preview = ", ".join(missing[:5])
        if len(missing) > 5:
            preview += ", ..."
        raise StepError(
            f"{label}: {len(missing)} taxa are not tips in the tree: {preview}"
        )
    result = np.zeros((counts.shape[0], len(tree.names)), dtype=np.float64)
    for column, name in enumerate(taxa):
        result[:, tips[str(name)]] = counts[:, column]
    for node in tree.postorder():
        parent = int(tree.parent[node])
        if parent >= 0:
            result[:, parent] += result[:, node]
    return result


def faith_pd_values(by_node: np.ndarray, length: np.ndarray) -> np.ndarray:
    """Faith's PD: sum of branch lengths on the union of root-to-tip paths."""
    return (length[None, :] * (by_node > 0)).sum(axis=1)


def unifrac_matrix(
    by_node: np.ndarray,
    length: np.ndarray,
    weighted: bool = False,
    totals: np.ndarray | None = None,
) -> np.ndarray:
    """Pairwise UniFrac distances between the rows of ``by_node``.

    ``by_node`` repeats every count at each ancestor, so weighted UniFrac
    must divide by the original per-sample totals, never by a row sum.
    """
    n = by_node.shape[0]
    if n == 0:
        raise StepError("unifrac: the abundance table has no samples")
    out = np.zeros((n, n), dtype=np.float64)
    if weighted:
        if totals is None:
            totals = by_node.sum(axis=1)
        totals = np.asarray(totals, dtype=np.float64)
        if totals.shape != (n,):
            raise StepError("unifrac: totals must hold one value per sample")
        proportions = np.zeros_like(by_node)
        nonzero = totals > 0
        proportions[nonzero] = by_node[nonzero] / totals[nonzero, None]
        for i in range(n):
            for j in range(i + 1, n):
                value = float(np.sum(length * np.abs(proportions[i] - proportions[j])))
                out[i, j] = out[j, i] = value
        return out
    present = by_node > 0
    for i in range(n):
        for j in range(i + 1, n):
            unique = np.logical_xor(present[i], present[j])
            observed = np.logical_or(present[i], present[j])
            observed_length = float(np.sum(length[observed]))
            value = 0.0 if observed_length == 0.0 else float(np.sum(length[unique])) / observed_length
            out[i, j] = out[j, i] = value
    return out


def tip_distances(tree: Tree) -> np.ndarray:
    """Patristic distance matrix between tips, in tip order."""
    order = tree.postorder()
    root_distance = np.zeros(len(tree.names), dtype=np.float64)
    depth = np.zeros(len(tree.names), dtype=np.int64)
    for node in reversed(order):
        parent = int(tree.parent[node])
        if parent >= 0:
            root_distance[node] = root_distance[parent] + tree.length[node]
            depth[node] = depth[parent] + 1
    tips = tree.tips
    n = len(tips)
    out = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            left, right = tips[i], tips[j]
            while depth[left] > depth[right]:
                left = int(tree.parent[left])
            while depth[right] > depth[left]:
                right = int(tree.parent[right])
            while left != right:
                left = int(tree.parent[left])
                right = int(tree.parent[right])
            out[i, j] = out[j, i] = (
                root_distance[tips[i]] + root_distance[tips[j]] - 2.0 * root_distance[left]
            )
    return out
