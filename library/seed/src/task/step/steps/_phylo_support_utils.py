"""Bootstrap support for neighbour-joining trees (JC69, complete deletion)."""
from __future__ import annotations

import math

import numpy as np

from src.core import StepError
from ._phylo_infer import aligned_sequences, neighbor_joining

SEPARATOR = "|"
_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "U": 3}


def _column_safe(records):
    columns = []
    for column in range(len(records[0][1])):
        bases = [sequence[column] for _, sequence in records]
        if all(base in _CODES for base in bases):
            columns.append(column)
    if len(columns) < 3:
        raise StepError("phylo_bootstrap: fewer than three comparable alignment columns")
    return columns


def encode(records):
    columns = _column_safe(records)
    matrix = np.full((len(records), len(columns)), -1, dtype=np.int8)
    for row, (_, sequence) in enumerate(records):
        matrix[row] = [_CODES.get(sequence[column], -1) for column in columns]
    return matrix, [name for name, _ in records]


def _jc69(matrix):
    count = matrix.shape[0]
    distances = np.zeros((count, count), dtype=np.float64)
    for i in range(count):
        for j in range(i + 1, count):
            both = (matrix[i] >= 0) & (matrix[j] >= 0)
            sites = int(both.sum())
            if sites == 0:
                raise StepError("phylo_bootstrap: a pair has no comparable sites")
            p = float(np.count_nonzero(matrix[i][both] != matrix[j][both])) / sites
            if p >= 0.75:
                distances[i, j] = distances[j, i] = 10.0
                continue
            distances[i, j] = distances[j, i] = -0.75 * math.log(1.0 - 4.0 * p / 3.0)
    return distances


def split_label(side, tips):
    left = frozenset(side)
    right = frozenset(tips) - left
    if len(left) > len(right):
        left = right
    elif len(left) == len(right) and tuple(sorted(right)) < tuple(sorted(left)):
        left = right
    return SEPARATOR.join(sorted(left))


def edge_children(edges):
    children = {name: [] for name, _, _ in edges}
    parent = {}
    length = {}
    for name, above, value in edges:
        parent[name] = above
        length[name] = float(value)
        if above is not None and above in children:
            children[above].append(name)
    roots = [name for name in children if parent.get(name) is None]
    if len(roots) != 1:
        raise StepError("phylo_bootstrap: the tree must have exactly one root")
    return children, parent, length, roots[0]


def descendant_tips(children, name):
    tips = set()
    stack = [name]
    while stack:
        node = stack.pop()
        if not children[node]:
            tips.add(node)
        else:
            stack.extend(children[node])
    return tips


def edge_splits(edges, tips):
    children, _, length, root = edge_children(edges)
    result = {}
    for name in children:
        if name == root or not children[name]:
            continue
        below = descendant_tips(children, name)
        if len(below) < 2 or len(below) > len(tips) - 2:
            continue
        result[split_label(below, tips)] = float(length[name])
    return result


def bootstrap(records, resamples=100, seed=0):
    if resamples < 1:
        raise StepError("phylo_bootstrap: resamples must be at least 1")
    matrix, names = encode(records)
    columns = matrix.shape[1]
    rng = np.random.default_rng(int(seed))
    reference = neighbor_joining(_jc69(matrix), names)[0]
    reference_splits = edge_splits(reference, names)
    counts = {label: 0 for label in reference_splits}
    for _ in range(int(resamples)):
        pick = rng.integers(0, columns, columns)
        edges, _ = neighbor_joining(_jc69(matrix[:, pick]), names)
        for label in edge_splits(edges, names):
            if label in counts:
                counts[label] += 1
    support = {label: counts[label] / float(resamples) for label in reference_splits}
    return reference, names, reference_splits, support


def read_support(form, split_dim, statistic_dim, field):
    if split_dim not in form.dims:
        raise StepError(f"phylo_support_filter: tree table lacks the {split_dim!r} dimension")
    labels = form.labels.get(split_dim) or {}
    fields = form.labels.get(statistic_dim) or {}
    if field not in fields:
        raise StepError(f"phylo_support_filter: support table lacks the {field!r} column")
    column = int(fields[field])
    values = {}
    for label, position in labels.items():
        values[str(label)] = float(form.data[int(position), column])
    return values
