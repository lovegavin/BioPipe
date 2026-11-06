"""Distance models, neighbour joining and split comparison for phylogeny."""

from __future__ import annotations

import math

import numpy as np

from src.core import StepError
from ._annotation_utils import fasta_sequences

_CANONICAL = set("ACGTU")
_TRANSITIONS = {frozenset("AG"), frozenset("CT")}


def aligned_sequences(form, sequence_dim, position_dim, step_name):
    """Return ``[(name, aligned_sequence)]`` with equal alignment lengths."""
    names, sequences = fasta_sequences(form, sequence_dim, position_dim, step_name)
    if len(sequences) < 3:
        raise StepError(f"{step_name}: at least three aligned sequences are required")
    lengths = {len(sequence) for sequence in sequences}
    if len(lengths) != 1:
        raise StepError(
            f"{step_name}: sequences are not aligned; lengths {sorted(lengths)[:5]}"
        )
    return list(zip(names, [sequence.upper() for sequence in sequences]))


def usable_columns(records, model):
    """Columns with a canonical base in every sequence (complete deletion)."""
    length = len(records[0][1])
    keep = []
    for column in range(length):
        bases = [sequence[column] for _, sequence in records]
        if model == "protein":
            if all(base.isalpha() and base not in "-.X*" for base in bases):
                keep.append(column)
        elif all(base in _CANONICAL for base in bases):
            keep.append(column)
    return keep


def _pair_columns(a, b, model):
    if model == "protein":
        return [
            (x, y) for x, y in zip(a, b)
            if x.isalpha() and y.isalpha() and x not in "-.X*" and y not in "-.X*"
        ]
    return [(x, y) for x, y in zip(a, b) if x in _CANONICAL and y in _CANONICAL]


def pair_distance(a, b, model, deletion):
    if deletion == "complete":
        pairs = list(zip(a, b))
        if model == "protein":
            pairs = [(x, y) for x, y in pairs if x.isalpha() and y.isalpha() and x not in "-.X*" and y not in "-.X*"]
        else:
            pairs = [(x, y) for x, y in pairs if x in _CANONICAL and y in _CANONICAL]
    else:
        pairs = _pair_columns(a, b, model)
    sites = len(pairs)
    if sites == 0:
        return float("nan")
    if model == "protein":
        differences = sum(1 for x, y in pairs if x != y)
        return differences / sites
    differences = sum(1 for x, y in pairs if x != y)
    p = differences / sites
    if model == "p":
        return p
    if model == "jc69":
        value = 1.0 - 4.0 * p / 3.0
        if value <= 0.0:
            raise StepError("phylo_distance_matrix: JC69 is undefined for p >= 0.75")
        return -0.75 * math.log(value)
    if model == "k2p":
        transitions = sum(
            1 for x, y in pairs if x != y and frozenset((x, y)) in _TRANSITIONS
        )
        transversions = differences - transitions
        pp = transitions / sites
        qq = transversions / sites
        first = 1.0 - 2.0 * pp - qq
        second = 1.0 - 2.0 * qq
        if first <= 0.0 or second <= 0.0:
            raise StepError("phylo_distance_matrix: K2P is undefined for saturated pairs")
        return -0.5 * math.log(first) - 0.25 * math.log(second)
    raise StepError(f"phylo_distance_matrix: unknown model {model!r}")


def distance_matrix(records, model, deletion):
    count = len(records)
    matrix = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        for j in range(i + 1, count):
            value = pair_distance(records[i][1], records[j][1], model, deletion)
            matrix[i, j] = matrix[j, i] = value
    if not np.all(np.isfinite(matrix)):
        raise StepError("phylo_distance_matrix: some pairs have no comparable sites")
    return matrix


def neighbor_joining(matrix, names):
    """Saitou-Nei neighbour joining; returns (edges, newick)."""
    count = len(names)
    if matrix.shape != (count, count):
        raise StepError("phylo_neighbor_joining: distance matrix is not square")
    if not np.allclose(matrix, matrix.T, atol=1e-9):
        raise StepError("phylo_neighbor_joining: distance matrix must be symmetric")
    if np.any(matrix < 0):
        raise StepError("phylo_neighbor_joining: distances must be non-negative")
    nodes = list(names)
    distances = matrix.astype(np.float64).copy()
    parents: dict[str, str | None] = {name: None for name in names}
    lengths: dict[str, float] = {name: 0.0 for name in names}
    counter = 0
    while len(nodes) > 2:
        n = len(nodes)
        total = distances.sum(axis=1)
        best = None
        for i in range(n):
            for j in range(i + 1, n):
                q = (n - 2) * distances[i, j] - total[i] - total[j]
                if best is None or q < best[0]:
                    best = (q, i, j)
        _, i, j = best
        d_ij = distances[i, j]
        li = 0.5 * d_ij + (total[i] - total[j]) / (2.0 * (n - 2))
        lj = d_ij - li
        counter += 1
        internal = f"N{counter}"
        while internal in parents:
            counter += 1
            internal = f"N{counter}"
        parents[nodes[i]] = internal
        parents[nodes[j]] = internal
        lengths[nodes[i]] = float(li)
        lengths[nodes[j]] = float(lj)
        parents[internal] = None
        lengths[internal] = 0.0
        new_row = (distances[i, :] + distances[j, :] - d_ij) / 2.0
        keep = [k for k in range(n) if k not in (i, j)]
        nodes = [nodes[k] for k in keep] + [internal]
        block = np.zeros((len(keep) + 1, len(keep) + 1), dtype=np.float64)
        block[:-1, :-1] = distances[np.ix_(keep, keep)]
        block[:-1, -1] = block[-1, :-1] = new_row[keep]
        distances = block
    if len(nodes) == 2:
        root = "Root"
        parents[nodes[0]] = root
        parents[nodes[1]] = root
        lengths[nodes[0]] = float(distances[0, 1] / 2.0)
        lengths[nodes[1]] = float(distances[0, 1] / 2.0)
        parents[root] = None
        lengths[root] = 0.0
    else:
        root = nodes[0]
        parents[root] = None
        lengths[root] = 0.0

    order = sorted(parents, key=lambda name: (name not in names, name))
    newick = _to_newick(root, parents, lengths)
    edges = [(name, parents[name], lengths[name]) for name in order]
    return edges, newick + ";"


def _to_newick(name, parents, lengths):
    children = {}
    for node, parent in parents.items():
        if parent is not None:
            children.setdefault(parent, []).append(node)

    def render(node):
        kids = children.get(node, [])
        if kids:
            body = "(" + ",".join(render(kid) for kid in kids) + ")"
        else:
            body = node
        if parents.get(node) is None:
            return body
        return f"{body}:{lengths.get(node, 0.0):.10g}"

    return render(name)


def splits(tree):
    """Non-trivial bipartitions (as tip-name sets) mapped to branch lengths."""
    tips = {tree.names[index] for index in tree.tips}
    total = len(tips)
    found = {}
    for node in range(len(tree.names)):
        if node == tree.root or node in tree.tips:
            continue
        below = {tree.names[index] for index in _descendant_tips(tree, node)}
        if len(below) < 2 or len(below) > total - 2:
            continue
        complement = tips - below
        left = tuple(sorted(below))
        right = tuple(sorted(complement))
        side = frozenset(below) if left <= right else frozenset(complement)
        found[side] = float(tree.length[node])
    return found


def _descendant_tips(tree, node):
    result = set()
    stack = [node]
    while stack:
        current = stack.pop()
        if current in tree.tips:
            result.add(current)
        stack.extend(tree.children[current])
    return result


def robinson_foulds(tree_a, tree_b):
    if set(tree_a.names[index] for index in tree_a.tips) != set(tree_b.names[index] for index in tree_b.tips):
        raise StepError("phylo_tree_distance: trees do not share the same tip set")
    splits_a = splits(tree_a)
    splits_b = splits(tree_b)
    shared = set(splits_a) & set(splits_b)
    only_a = set(splits_a) - set(splits_b)
    only_b = set(splits_b) - set(splits_a)
    rf = len(only_a) + len(only_b)
    n_tips = len(tree_a.tips)
    max_rf = 2 * (n_tips - 3)
    branch_score = math.sqrt(
        sum((splits_a[key] - splits_b[key]) ** 2 for key in shared)
        + sum(splits_a[key] ** 2 for key in only_a)
        + sum(splits_b[key] ** 2 for key in only_b)
    )
    return {
        "n_tips": n_tips,
        "rf": rf,
        "max_rf": max_rf,
        "normalized_rf": rf / max_rf if max_rf else 0.0,
        "shared_splits": len(shared),
        "splits_a": len(splits_a),
        "splits_b": len(splits_b),
        "branch_score": branch_score,
        "identical": rf == 0,
    }
