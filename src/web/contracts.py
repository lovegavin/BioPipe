"""Cheap contract analysis of a partial canvas. No source payloads are read."""
from collections import deque

from src.core.contracts import VERSION, compatible, infer_output, resolve, source_schema, unknown
from src.reader import READERS, primary_ext


def analyze_graph(graph, catalog, root, *, source_overrides=None, ancestry=()):
    from .graph import GraphError, project_path
    from .routes import check_interface, require_route, port_index
    if len(ancestry) > 6:
        raise GraphError("路线嵌套最多支持 6 层。")
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
            if source_overrides and node.id in source_overrides:
                schema = source_overrides[node.id]
            elif source:
                schema.update(dims=source.dims, ndim=len(source.dims))
                path = project_path(root, source.path, graph.base_dir)
                # A BED filename alone cannot distinguish PLINK from intervals.
                # Use sibling routing only when the source actually exists.
                candidates = [reader for reader in catalog["readers"] if primary_ext(path) in reader["extensions"]
                              and (not path.is_file() or (all(path.with_suffix(s).exists() for s in reader.get("requires_siblings", []))
                              and not any(path.with_suffix(s).exists() for s in reader.get("excludes_siblings", []))))]
                if len(candidates) == 1:
                    reader = candidates[0]
                    if reader["name"] == "TxtReader":
                        name = source.args.get("reader", "csv")
                        delegates = [item for item in catalog["readers"] if isinstance(name, str)
                                     and item["name"] != "TxtReader" and name.lower() in
                                     (item["name"].lower(), item["name"].removesuffix("Reader").lower())]
                        if len(delegates) != 1:
                            raise GraphError("TxtReader 的 reader 参数无效。", node.id)
                        reader = delegates[0]
                    schema = source_schema(reader["output_contract"], source.dims)
                    schema["reader"] = reader["name"]
            ports[node.id] = {"inputs": [], "outputs": [schema]}
        elif node.kind == "route":
            route = require_route(node)
            if route.id in ancestry:
                raise GraphError("路线不能递归调用自身。", node.id)
            check_interface(route.graph, catalog)
            interface = route.graph.interface
            ports[node.id] = {"inputs": [port.contract or None for port in interface.inputs],
                              "outputs": [unknown() for _ in interface.outputs]}
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
        if node.kind != "source":
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
            if node.kind == "route":
                route = require_route(node)
                overrides = {port.node_id: inputs[i] for i, port in enumerate(route.graph.interface.inputs)}
                try:
                    inner = analyze_graph(route.graph, catalog, root, source_overrides=overrides, ancestry=(*ancestry, route.id))
                except GraphError as exc:
                    raise GraphError(f"{node.title or route.name}：{exc}", key) from exc
                failures = [check for check in inner["edges"] if check["status"] == "incompatible"]
                if failures:
                    for check in results:
                        if check["target"] == key:
                            check["status"] = "incompatible"
                            check["reasons"] = list(dict.fromkeys(reason for failure in failures for reason in failure["reasons"]))
                ports[key]["outputs"] = [inner["nodes"][port.node_id]["outputs"][port_index(port.handle)]
                                          if not invalid and not failures else unknown() for port in route.graph.interface.outputs]
            elif ports[key]["outputs"]:
                spec = registry[node.operator]
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
