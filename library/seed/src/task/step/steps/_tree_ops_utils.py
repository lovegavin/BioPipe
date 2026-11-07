"""Helpers shared by the tree manipulation operators.

Trees travel through the graph as ``node x field`` forms with the fields
``parent``, ``branch_length``, ``depth`` and ``is_leaf``.  The helpers below
convert such a form into mutable :class:`TreeNode` graphs, edit the graph and
encode it again with :func:`build_tree_form`.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError

from ._phylo_common import load_tree
from ._tree_build_common import TreeNode, _InternalNamer, build_tree_form


def tree_from_form(form, node_dim: str, field_dim: str, label: str):
    """Return the mutable root node of a tree form."""
    return nodes_from_tree(load_tree(form, node_dim, field_dim, label))


def nodes_from_tree(tree) -> TreeNode:
    """Build a mutable ``TreeNode`` graph from a parsed tree."""
    nodes = []
    for index, name in enumerate(tree.names):
        node = TreeNode(str(name))
        node.length = float(tree.length[index])
        nodes.append(node)
    for index in range(len(nodes)):
        for child in tree.children[index]:
            nodes[child].parent = nodes[index]
            nodes[index].children.append(nodes[child])
    return nodes[tree.root]


def walk(root: TreeNode):
    """Yield every node once, root first (breadth first)."""
    queue = [root]
    while queue:
        node = queue.pop(0)
        yield node
        queue.extend(node.children)


def tip_nodes(root: TreeNode) -> list[TreeNode]:
    return [node for node in walk(root) if not node.children]


def internal_nodes(root: TreeNode) -> list[TreeNode]:
    return [node for node in walk(root) if node.children]


def detach(node: TreeNode) -> None:
    """Remove ``node`` from its parent's children (if it has a parent)."""
    if node.parent is not None:
        node.parent.children.remove(node)
        node.parent = None


def path_to_root(node: TreeNode) -> list[TreeNode]:
    chain = []
    while node is not None:
        chain.append(node)
        node = node.parent
    return chain


def node_distance(a: TreeNode, b: TreeNode) -> float:
    """Sum of branch lengths on the path between two nodes."""
    up = {}
    total = 0.0
    node = a
    while node is not None:
        up[id(node)] = total
        if node.parent is None:
            break
        total += node.length
        node = node.parent
    total = 0.0
    node = b
    while node is not None:
        if id(node) in up:
            return total + up[id(node)]
        total += node.length
        node = node.parent
    raise StepError("tree: nodes are not connected")


def tree_diameter(root: TreeNode):
    """Return ``(distance, tip_a, tip_b)`` for the longest tip-tip path."""
    tips = tip_nodes(root)
    if len(tips) < 2:
        raise StepError("tree_root_midpoint: need at least two tips")
    best = -1.0
    pair = (tips[0], tips[1])
    for i in range(len(tips)):
        for j in range(i + 1, len(tips)):
            distance = node_distance(tips[i], tips[j])
            if distance > best:
                best = distance
                pair = (tips[i], tips[j])
    return best, pair[0], pair[1]


def reroot_at(old_root: TreeNode, new_root: TreeNode) -> TreeNode:
    """Reverse the parent/child direction along the path to ``new_root``."""
    chain = path_to_root(new_root)
    lengths = [node.length for node in chain]
    for index in range(len(chain) - 1):
        lower = chain[index]
        upper = chain[index + 1]
        upper.children.remove(lower)
        lower.children.append(upper)
        upper.parent = lower
        upper.length = lengths[index]
    chain[0].parent = None
    chain[0].length = np.nan
    return new_root


def split_edge(parent: TreeNode, child: TreeNode, length: float, namer: _InternalNamer) -> TreeNode:
    """Insert a new root on the edge ``parent -> child`` at ``length`` above child."""
    edge = child.length
    if length <= 0.0 or length >= edge:
        raise StepError("tree_root_midpoint: the midpoint does not fall inside an edge")
    parent.children.remove(child)
    root = TreeNode(namer.next())
    root.length = np.nan
    root.parent = None
    child.parent = root
    child.length = float(length)
    parent.parent = root
    parent.length = float(edge - length)
    root.children = [child, parent]
    return root


def suppress_unary(root: TreeNode) -> TreeNode:
    """Remove unary internal nodes by merging the two incident edges."""
    changed = True
    while changed:
        changed = False
        for node in list(walk(root)):
            if node is root or len(node.children) != 1:
                continue
            child = node.children[0]
            parent = node.parent
            if parent is None:
                continue
            parent.children.remove(node)
            parent.children.append(child)
            child.parent = parent
            child.length = float(child.length) + float(node.length)
            node.parent = None
            node.children = []
            changed = True
        if len(root.children) == 1:
            child = root.children[0]
            child.parent = None
            child.length = np.nan
            root.children = []
            root = child
            changed = True
    return root


def _midpoint_root(root: TreeNode) -> TreeNode:
    """Root the tree at the midpoint of its longest tip-to-tip path."""
    diameter, a, b = tree_diameter(root)
    if diameter <= 0.0:
        raise StepError("tree_root_midpoint: the tree has zero diameter")
    namer = _InternalNamer([node.name for node in walk(root)])
    up_a = path_to_root(a)
    up_b = path_to_root(b)
    common = set(id(n) for n in up_b)
    lca = None
    for candidate in up_a:
        if id(candidate) in common:
            lca = candidate
            break
    assert lca is not None
    path = []
    node = a
    while node is not lca:
        path.append(node)
        node = node.parent
    path.append(lca)
    tail = []
    node = b
    while node is not lca:
        tail.append(node)
        node = node.parent
    path.extend(reversed(tail))

    half = diameter / 2.0
    travelled = 0.0
    for i in range(len(path) - 1):
        lower = path[i]
        upper = path[i + 1]
        if lower.parent is upper:
            edge = float(lower.length)
        elif upper.parent is lower:
            edge = float(upper.length)
        else:
            raise StepError("tree_root_midpoint: the diameter path is not connected")
        if travelled + edge >= half - 1e-12:
            offset = half - travelled
            if offset <= 1e-12:
                return reroot_at(root, lower)
            if edge - offset <= 1e-9:
                return reroot_at(root, upper)
            # Re-root at upper first so that lower is a child of upper.
            rooted = reroot_at(root, upper)
            return split_edge(upper, lower, offset, namer)
        travelled += edge
    return reroot_at(root, path[-1])


def midpoint_root(root: TreeNode) -> TreeNode:
    return suppress_unary(_midpoint_root(root))


def prune_tips(root: TreeNode, remove: set[str]) -> TreeNode:
    """Remove tips by name, suppressing empty and unary internal nodes."""
    tips = {node.name for node in tip_nodes(root)}
    missing = sorted(name for name in remove if name not in tips)
    if missing:
        raise StepError(
            "tree_prune_tips: unknown tip(s): " + ", ".join(missing[:5])
        )
    if len(remove) >= len(tips):
        raise StepError("tree_prune_tips: cannot remove every tip of the tree")
    internal_ids = {id(node) for node in walk(root) if node.children}
    for node in list(walk(root)):
        if node.name in remove and not node.children:
            detach(node)

    changed = True
    while changed:
        changed = False
        for node in list(walk(root)):
            if node is root or id(node) not in internal_ids:
                continue
            if node.children:
                continue
            detach(node)
            changed = True
        for node in list(walk(root)):
            if node is root or id(node) not in internal_ids or len(node.children) != 1:
                continue
            child = node.children[0]
            parent = node.parent
            if parent is None:
                continue
            parent.children.remove(node)
            parent.children.append(child)
            child.parent = parent
            child.length = child.length + node.length
            node.parent = None
            node.children = []
            changed = True
        if len(root.children) == 1:
            child = root.children[0]
            child.parent = None
            child.length = np.nan
            root.children = []
            root = child
            changed = True
    remaining = [node for node in walk(root) if not node.children]
    if not remaining:
        raise StepError("tree_prune_tips: no tips left after pruning")
    return root


def _subtree_size(node: TreeNode) -> int:
    total = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if current.children:
            stack.extend(current.children)
        else:
            total += 1
    return total


def balance_stats(root: TreeNode) -> dict:
    tips = tip_nodes(root)
    n = len(tips)
    depth = {id(root): 0}
    stack = [root]
    while stack:
        node = stack.pop()
        for child in node.children:
            depth[id(child)] = depth[id(node)] + 1
            stack.append(child)
    sackin = sum(depth[id(tip)] for tip in tips)
    internals = internal_nodes(root)
    binary = all(len(node.children) == 2 for node in internals)
    colless = None
    normalized = None
    if binary and n >= 3:
        colless = 0
        for node in internals:
            left, right = node.children
            colless += abs(_subtree_size(left) - _subtree_size(right))
        normalized = colless / ((n - 1) * (n - 2) / 2.0)
    cherries = 0
    for node in internals:
        if len(node.children) == 2 and all(not child.children for child in node.children):
            cherries += 1
    return {
        "n_tips": n,
        "n_internal": len(internals),
        "sackin": sackin,
        "colless": colless,
        "normalized_colless": normalized,
        "cherries": cherries,
        "binary": binary,
    }


def encode_tree(root: TreeNode, node_dim: str, field_dim: str, label: str):
    return build_tree_form(root, node_dim, field_dim, label)


def newick_from_nodes(root: TreeNode, namer: _InternalNamer | None = None) -> str:
    """Small Newick writer used for oracle hand-off files."""
    def label(node: TreeNode) -> str:
        return node.name

    def render(node: TreeNode) -> str:
        if not node.children:
            text = label(node)
        else:
            text = "(" + ",".join(render(child) for child in node.children) + ")"
            text += label(node)
        if node.parent is not None and np.isfinite(node.length):
            text += ":" + repr(float(node.length))
        return text

    return render(root) + ";"
