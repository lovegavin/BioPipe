"""Shared helpers for distance-based tree builders.

Tree builders produced by this package encode a rooted tree as a
``node x field`` form with exactly the fields used by
``src/reader/readers/newick_reader.py``:

    parent          label encoder code for the parent node (root = None)
    branch_length   length of the edge above the node (root = NaN)
    depth           nesting depth below the root (root = 0)
    is_leaf         1 for tips, 0 for internal nodes

The ``parent`` column is integer-valued but stored as float32; the
encoder mapping travels in ``info["encoders"][field_dim]["parent"]`` so
the table can be decoded by :func:`src.task.step.steps._phylo_common.load_tree`.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.reader.readers._labels import unique_labels

from ._stats20_common import distance


class TreeNode:
    """Minimal tree node used while a builder assembles its topology."""

    __slots__ = ("name", "parent", "length", "children", "height", "size")

    def __init__(self, name: str) -> None:
        self.name = name
        self.parent: "TreeNode | None" = None
        self.length = np.nan
        self.children: list[TreeNode] = []
        self.height = 0.0
        self.size = 1


class _InternalNamer:
    """Allocate deterministic internal node names that cannot collide."""

    def __init__(self, existing) -> None:
        self.used = set(existing)
        self.index = 0

    def next(self) -> str:
        while True:
            name = f"Internal{self.index}"
            self.index += 1
            if name not in self.used:
                self.used.add(name)
                return name


def distance_input(form: Form, dim: str, dim_b: str, label: str) -> tuple[np.ndarray, list[str]]:
    """Validate a symmetric pairwise distance matrix and return it with taxa names."""
    matrix, names = distance(form, dim, dim_b, label)
    if len(names) < 2:
        raise StepError(f"{label}: need at least two taxa")
    if not np.allclose(np.diag(matrix), 0.0, atol=1e-8):
        raise StepError(f"{label}: distance matrix diagonal must be zero")
    if np.any(matrix < 0):
        raise StepError(f"{label}: distances must be nonnegative")
    return np.asarray(matrix, dtype=np.float64), names


def build_tree_form(
    root: TreeNode,
    node_dim: str,
    field_dim: str,
    label: str,
    negative: int = 0,
) -> Form:
    """Encode a rooted tree as a node x field form.

    Nodes are emitted in postorder (children before parent), which is the
    order produced by ``NewickReader`` and accepted by ``load_tree``.
    """
    ordered: list[TreeNode] = []
    depths: dict[int, int] = {}

    def walk(node: TreeNode, level: int) -> None:
        depths[id(node)] = level
        for child in node.children:
            walk(child, level + 1)
        ordered.append(node)

    walk(root, 0)
    names = [node.name for node in ordered]
    labels = unique_labels(names, node_dim, label)
    parent_encoder = get_encoder("labelencoder")
    parent_names = [None if node.parent is None else node.parent.name for node in ordered]
    parent_codes = np.asarray(parent_encoder.fit_transform(parent_names), dtype=np.float64)
    lengths = np.asarray(
        [np.nan if node.parent is None else float(node.length) for node in ordered],
        dtype=np.float64,
    )
    depth_values = np.asarray([float(depths[id(node)]) for node in ordered], dtype=np.float64)
    leaf_values = np.asarray([0.0 if node.children else 1.0 for node in ordered], dtype=np.float64)
    data = np.column_stack([parent_codes, lengths, depth_values, leaf_values])
    info = {
        "missing_code": np.nan,
        "encoders": {field_dim: {"parent": parent_encoder}},
    }
    if negative:
        info["negative_branches_clipped"] = int(negative)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=[node_dim, field_dim],
        labels={
            node_dim: labels,
            field_dim: unique_labels(
                ["parent", "branch_length", "depth", "is_leaf"], field_dim, label
            ),
        },
        info=info,
    )
