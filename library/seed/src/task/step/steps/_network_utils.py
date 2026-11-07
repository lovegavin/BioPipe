"""Undirected biological network utilities (centrality, topology, communities)."""
from __future__ import annotations

import math
from collections import deque

import numpy as np

from src.core.errors import StepError


def read_edges(form, edge_dim, field_dim, node_a_field="node_a", node_b_field="node_b",
               weight_field="", operator="network"):
    dims = list(form.dims)
    if len(dims) != 2:
        raise StepError(f"{operator}: expected a two-dimensional edge table")
    fields = form.labels[field_dim]
    if node_a_field not in fields or node_b_field not in fields:
        raise StepError(f"{operator}: missing node columns '{node_a_field}' / '{node_b_field}'")
    data = np.asarray(form.data)
    if data.ndim != 2:
        raise StepError(f"{operator}: edge table must be two-dimensional")

    names = list(form.labels[edge_dim])
    weight_col = -1
    if weight_field:
        if weight_field not in fields:
            raise StepError(f"{operator}: missing weight column '{weight_field}'")
        weight_col = fields[weight_field]
    a_col = fields[node_a_field]
    b_col = fields[node_b_field]
    encoders = (form.info or {}).get("encoders", {}).get(field_dim, {}) or {}

    def decode(field_name, row_index):
        code = int(round(float(data[row_index, fields[field_name]])))
        encoder = encoders.get(field_name) if isinstance(encoders, dict) else None
        inverse = getattr(encoder, "inverse", None) if encoder is not None else None
        if inverse:
            return str(inverse.get(code, code))
        return str(code)

    edges = []
    nodes = set()
    for index in range(data.shape[0]):
        a_name = decode(node_a_field, index)
        b_name = decode(node_b_field, index)
        if a_name == b_name:
            continue
        weight = 1.0
        if weight_col >= 0:
            try:
                weight = float(data[index, weight_col])
            except (TypeError, ValueError) as exc:
                raise StepError(f"{operator}: edge row {index} has an invalid weight") from exc
            if not math.isfinite(weight) or weight <= 0:
                weight = 1.0
        edges.append((a_name, b_name, weight))
        nodes.add(a_name)
        nodes.add(b_name)
    if not nodes:
        raise StepError(f"{operator}: no edges remained after filtering")
    return sorted(nodes), edges


def adjacency(nodes, edges):
    graph = {name: {} for name in nodes}
    for a_name, b_name, weight in edges:
        graph[a_name][b_name] = graph[a_name].get(b_name, 0.0) + weight
        graph[b_name][a_name] = graph[b_name].get(a_name, 0.0) + weight
    return graph


def degrees(graph):
    return {name: float(len(neighbours)) for name, neighbours in graph.items()}


def component_sizes(graph):
    seen = set()
    sizes = []
    for start in sorted(graph):
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        size = 0
        while queue:
            current = queue.popleft()
            size += 1
            for neighbour in graph[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        sizes.append(size)
    return sorted(sizes, reverse=True)


def bfs_distances(graph, start):
    distances = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in graph[current]:
            if neighbour not in distances:
                distances[neighbour] = distances[current] + 1
                queue.append(neighbour)
    return distances


def shortest_paths(graph, start):
    """Yield (node, distance, number_of_shortest_paths) via Brandes BFS."""
    distances = {start: 0}
    counts = {start: 1.0}
    queue = deque([start])
    order = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbour in graph[current]:
            if neighbour not in distances:
                distances[neighbour] = distances[current] + 1
                queue.append(neighbour)
            if distances[neighbour] == distances[current] + 1:
                counts[neighbour] = counts.get(neighbour, 0.0) + counts[current]
    return order, distances, counts


def betweenness(graph):
    score = {name: 0.0 for name in graph}
    for source in graph:
        order, distances, counts = shortest_paths(graph, source)
        dependency = {name: 0.0 for name in graph}
        for node in reversed(order):
            if node == source:
                continue
            for neighbour in graph[node]:
                if distances.get(neighbour) == distances[node] - 1:
                    dependency[neighbour] += counts[neighbour] / counts[node] * (1.0 + dependency[node])
            score[node] += dependency[node]
    n = len(graph)
    for name in score:
        if n > 2:
            score[name] *= 1.0 / ((n - 1) * (n - 2))
    return score


def closeness(graph):
    n = len(graph)
    score = {}
    for name in graph:
        distances = bfs_distances(graph, name)
        reachable = len(distances) - 1
        total = sum(distances.values())
        if total <= 0:
            score[name] = 0.0
        else:
            score[name] = (reachable / total) * (reachable / (n - 1)) if n > 1 else 0.0
    return score


def eigenvector(graph, iterations=500, tolerance=1e-12):
    names = list(graph)
    index = {name: position for position, name in enumerate(names)}
    n = len(names)
    vector = np.full(n, 1.0 / math.sqrt(n))
    for _ in range(iterations):
        updated = np.zeros(n)
        for name, neighbours in graph.items():
            for neighbour in neighbours:
                updated[index[name]] += vector[index[neighbour]]
        norm = float(np.linalg.norm(updated))
        if norm == 0.0:
            return {name: 0.0 for name in names}
        updated /= norm
        if float(np.abs(updated - vector).sum()) < tolerance:
            vector = updated
            break
        vector = updated
    return {name: float(vector[index[name]]) for name in names}


def pagerank(graph, damping=0.85, iterations=500, tolerance=1e-12):
    names = list(graph)
    n = len(names)
    rank = {name: 1.0 / n for name in names}
    for _ in range(iterations):
        updated = {}
        dangling = sum(rank[name] for name in names if not graph[name])
        for name in names:
            total = 0.0
            for neighbour in graph[name]:
                total += rank[neighbour] / len(graph[neighbour])
            updated[name] = (1.0 - damping) / n + damping * (total + dangling / n)
        delta = sum(abs(updated[name] - rank[name]) for name in names)
        rank = updated
        if delta < tolerance:
            break
    return rank


def clustering_coefficient(graph):
    score = {}
    for name, neighbours in graph.items():
        degree = len(neighbours)
        if degree < 2:
            score[name] = 0.0
            continue
        links = 0
        for a_name in neighbours:
            for b_name in neighbours:
                if a_name < b_name and b_name in graph[a_name]:
                    links += 1
        score[name] = 2.0 * links / (degree * (degree - 1))
    return score


def degree_assortativity(graph):
    xs = []
    ys = []
    for name, neighbours in graph.items():
        for neighbour in neighbours:
            xs.append(float(len(neighbours)))
            ys.append(float(len(graph[neighbour])))
    if len(xs) < 2:
        return 0.0
    xs = np.asarray(xs)
    ys = np.asarray(ys)
    if xs.std() == 0 or ys.std() == 0:
        return 0.0
    return float(np.corrcoef(xs, ys)[0, 1])


def modularity(graph, communities):
    """Undirected modularity for a partition given as {node: community}."""
    two_m = sum(len(neighbours) for neighbours in graph.values())
    if two_m == 0:
        return 0.0
    totals = {}
    internal = {}
    for name, neighbours in graph.items():
        key = communities[name]
        totals[key] = totals.get(key, 0) + len(neighbours)
        for neighbour in neighbours:
            if communities[neighbour] == key:
                internal[key] = internal.get(key, 0) + 1
    score = 0.0
    for key, degree in totals.items():
        score += (internal.get(key, 0) / two_m) - (degree / two_m) ** 2
    return float(score)


def greedy_communities(graph, resolution=1.0, max_merges=None):
    """Clauset-Newman-Moore greedy modularity with a simple O(n^2) scan."""
    names = list(graph)
    assignment = {name: name for name in names}
    members = {name: {name} for name in names}
    degree = {name: float(len(graph[name])) for name in names}
    links = []
    for name, neighbours in graph.items():
        for neighbour in neighbours:
            if name < neighbour:
                links.append((name, neighbour))
    two_m = sum(degree.values())
    if two_m == 0:
        return {name: 0 for name in names}, 0.0

    def delta(a_key, b_key):
        left = members[a_key]
        right = members[b_key]
        between = 0
        for u, v in links:
            if (u in left and v in right) or (u in right and v in left):
                between += 1
        return between / two_m - resolution * degree[a_key] * degree[b_key] / (two_m ** 2)

    merges = 0
    while True:
        best = None
        keys = sorted(members)
        for i, a_key in enumerate(keys):
            for b_key in keys[i + 1:]:
                gain = delta(a_key, b_key)
                if best is None or gain > best[0]:
                    best = (gain, a_key, b_key)
        if best is None or best[0] <= 1e-12:
            break
        _, a_key, b_key = best
        for name in members[b_key]:
            assignment[name] = a_key
        members[a_key] |= members[b_key]
        degree[a_key] += degree[b_key]
        del members[b_key]
        del degree[b_key]
        merges += 1
        if max_merges and merges >= max_merges:
            break
    labelled = {}
    for position, key in enumerate(sorted(members)):
        for name in members[key]:
            labelled[name] = position
    return labelled, modularity(graph, labelled)


def summary_statistics(graph):
    n = len(graph)
    degrees_map = degrees(graph)
    sizes = component_sizes(graph)
    if n > 1:
        density = sum(degrees_map.values()) / (n * (n - 1))
    else:
        density = 0.0
    largest_nodes = None
    for name in sorted(graph):
        distances = bfs_distances(graph, name)
        if len(distances) == sizes[0]:
            largest_nodes = distances
            break
    diameter = 0.0
    if largest_nodes:
        for start in largest_nodes:
            local = bfs_distances(graph, start)
            diameter = max(diameter, max(local.values()))
    clustering = clustering_coefficient(graph)
    return {
        "n_nodes": float(n),
        "n_edges": float(sum(degrees_map.values()) / 2.0),
        "density": float(density),
        "n_components": float(len(sizes)),
        "largest_component": float(sizes[0]),
        "diameter": float(diameter),
        "average_degree": float(np.mean(list(degrees_map.values()))) if n else 0.0,
        "clustering_coefficient": float(np.mean(list(clustering.values()))) if n else 0.0,
        "assortativity": degree_assortativity(graph),
    }
