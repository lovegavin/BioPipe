"""Cheap contract analysis of a partial canvas. No source payloads are read."""
from collections import deque

from src.core.contracts import VERSION, compatible, infer_output, resolve, source_schema, unknown
from src.reader import READERS, primary_ext


def analyze_graph(graph, catalog, root):
    from .graph import GraphError, project_path
    registry = {item["name"]: item for item in catalog["operators"]}
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise GraphError("节点 ID 重复。")
    incoming = {key: {} for key in nodes}
    outgoing = {key: [] for key in nodes}
    degree = {key: 0 for key in nodes}
    ports, results = {}, []
    for node in graph.nodes:
        if node.kind == "source":
            source = node.source
            schema = unknown()
            if source:
                schema.update(dims=source.dims, ndim=len(source.dims))
                path = project_path(root, source.path, graph.base_dir)
                # A BED filename alone cannot distinguish PLINK from intervals.
                # Use sibling routing only when the source actually exists.
                candidates = [reader for reader in READERS if reader.matches(path)] if path.is_file() else [
                    reader for reader in READERS if primary_ext(path) in reader.extensions]
                if len(candidates) == 1:
                    reader = candidates[0]
                    schema = source_schema(reader.output_contract, source.dims)
                    schema["reader"] = type(reader).__name__
            ports[node.id] = {"inputs": [], "outputs": [schema]}
        else:
            spec = registry.get(node.operator)
            if spec is None:
                raise GraphError(f"未找到算子 {node.operator!r}。", node.id)
            count = node.input_count if spec["inputs_arity"] == "*" else spec["inputs_arity"]
            requirements = spec["contracts"]["inputs"] or []
            params = {**spec["runtime_defaults"], **node.params}
            ports[node.id] = {"inputs": [resolve(requirements[min(i, len(requirements)-1)], params) if requirements else None
                                         for i in range(count)],
                              "outputs": [unknown() for _ in range(1 if spec["output_parameter"] else len(spec["outputs"]))]}
    edge_ids = set()
    for edge in graph.edges:
        if edge.id in edge_ids:
            raise GraphError("连线 ID 重复。")
        edge_ids.add(edge.id)
        if edge.source not in nodes or edge.target not in nodes:
            raise GraphError("连线包含已不存在的节点。")
        port = int(edge.targetHandle[3:])
        output = 0 if edge.sourceHandle == "out" else int(edge.sourceHandle[4:]) if edge.sourceHandle.startswith("out-") and edge.sourceHandle[4:].isdigit() else -1
        if output < 0 or output >= len(ports[edge.source]["outputs"]) or port >= len(ports[edge.target]["inputs"]):
            raise GraphError("连线端口不存在。", edge.target)
        if port in incoming[edge.target]:
            raise GraphError("这个输入端口已有连线。", edge.target)
        incoming[edge.target][port] = (edge, output)
        outgoing[edge.source].append(edge.target)
        degree[edge.target] += 1
    queue = deque(key for key in nodes if degree[key] == 0)
    visited = 0
    while queue:
        key = queue.popleft()
        visited += 1
        node = nodes[key]
        if node.kind == "operator":
            inputs = [unknown() for _ in ports[key]["inputs"]]
            invalid = False
            for index, (edge, output) in incoming[key].items():
                inputs[index] = ports[edge.source]["outputs"][output]
                try:
                    result = compatible(inputs[index], ports[key]["inputs"][index])
                except (TypeError, ValueError, KeyError):
                    result = {"status": "unknown", "reasons": ["请完善算子参数后检查契约"]}
                invalid |= result["status"] == "incompatible"
                results.append({"id": edge.id, "source": edge.source, "target": key, **result})
            spec = registry[node.operator]
            if ports[key]["outputs"]:
                try:
                    schema = infer_output(spec["contracts"]["output"], inputs, {**spec["runtime_defaults"], **node.params}) if not invalid else unknown()
                except (TypeError, ValueError, KeyError):
                    schema = unknown()
                ports[key]["outputs"] = [schema for _ in ports[key]["outputs"]]
        for target in outgoing[key]:
            degree[target] -= 1
            if degree[target] == 0:
                queue.append(target)
    if visited != len(nodes):
        raise GraphError("工作流存在环路，请删除回连的连线。")
    return {"version": VERSION, "nodes": ports, "edges": results}
