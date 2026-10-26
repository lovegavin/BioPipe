"""Portable route snapshots, saved workflows, and expansion into the existing DAG.

Saving a workflow never registers it. The registry contains explicitly selected
snapshots; a running graph is self-contained and does not resolve mutable names.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import uuid

from .storage import FileLock, atomic_json

from .models import (Graph, GraphEdge, RouteDefinition, RouteInterface, RouteInput,
                     RouteOutput, SavedWorkflow, Workspace, LibraryState)


def fail(message, node_id=None):
    from .graph import GraphError
    raise GraphError(message, node_id)


def port_index(handle):
    if handle == "out":
        return 0
    if handle.startswith("out-") and handle[4:].isdigit():
        return int(handle[4:])
    fail("输出端口格式无效。")


def output_names(node, registry):
    if node.kind == "source":
        return [node.id]
    if node.kind == "route":
        definition = require_route(node)
        return [f"{node.id}__out_{i+1}" for i in range(len(definition.graph.interface.outputs))]
    spec = registry.get(node.operator)
    if spec is None:
        fail(f"未找到算子 {node.operator!r}。", node.id)
    return [str(node.params.get("output", node.id))] if spec["output_parameter"] else spec["outputs"]


def require_route(node):
    if node.route is None or node.route.graph.interface is None:
        fail("路线算子缺少版本快照或注册接口，请重新添加。", node.id)
    return node.route


def check_interface(graph, catalog):
    """Validate the boundary without requiring the original input files."""
    interface = graph.interface
    if interface is None:
        fail("保存的路线缺少注册接口。")
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        fail("路线节点 ID 重复。")
    inputs = [port.node_id for port in interface.inputs]
    sources = {node.id for node in graph.nodes if node.kind == "source"}
    if len(set(inputs)) != len(inputs) or set(inputs) != sources:
        fail("路线输入必须与内部数据源一一对应。")
    if not any(node.kind != "source" for node in graph.nodes):
        fail("路线至少需要一个处理算子。")
    registry = {item["id"]: item for item in catalog["operators"]}
    seen = set()
    for port in interface.outputs:
        key = (port.node_id, port_index(port.handle))
        if key in seen or port.node_id not in nodes:
            fail("路线输出端口重复或引用了不存在的节点。")
        if key[1] >= len(output_names(nodes[port.node_id], registry)):
            fail("路线输出引用的节点没有这个数据端口。", port.node_id)
        seen.add(key)


def prepare_interface(graph, catalog, root):
    """Attach an editable interface even to an incomplete saved canvas."""
    from .contracts import analyze_graph
    result = graph.model_copy(deep=True)
    analysis = analyze_graph(result, catalog, root)
    old = result.interface
    previous_inputs = {p.node_id: p for p in old.inputs} if old else {}
    inputs = []
    for node in result.nodes:
        if node.kind == "source":
            previous = previous_inputs.get(node.id)
            schema = deepcopy(analysis["nodes"][node.id]["outputs"][0])
            schema.pop("reader", None)
            schema["labels"] = [{"dim": dim, "values": labels} for dim, labels in schema.get("labels", {}).items() if labels]
            schema["parallel"] = [{"dim": dim, "fields": fields} for dim, fields in schema.pop("axis_info", {}).items() if fields]
            inputs.append(RouteInput(node_id=node.id, label=previous.label if previous else node.title or node.id, contract=schema))
    outputs = []
    if old:
        candidates = old.outputs
    else:
        # A data port consumed only by a report remains a useful route output.
        registry = {o["id"]: o for o in catalog["operators"]}
        nodes = {n.id: n for n in result.nodes}
        consumed = {(e.source, port_index(e.sourceHandle)) for e in result.edges
                    if e.target in nodes and output_names(nodes[e.target], registry)}
        candidates = [RouteOutput(node_id=n.id, handle="out" if len(analysis["nodes"][n.id]["outputs"]) == 1 else f"out-{i}",
                                  label=n.title or n.operator or n.id)
                      for n in result.nodes if n.kind != "source"
                      for i, _ in enumerate(analysis["nodes"][n.id]["outputs"]) if (n.id, i) not in consumed]
    for port in candidates:
        node_ports = analysis["nodes"].get(port.node_id, {}).get("outputs", [])
        index = port_index(port.handle)
        if index < len(node_ports):
            outputs.append(port.model_copy(update={"contract": deepcopy(node_ports[index])}))
    result.schema_version = 2
    result.interface = RouteInterface(inputs=inputs, outputs=outputs)
    return result


def expand_routes(graph, catalog):
    """Inline route bodies with unique IDs/names; return node ownership for UI.

    Input sources in a route are placeholders, never read from disk. Each route
    body participates in the same memory plan and deterministic ordering as the
    outer DAG. Snapshots, nesting depth, and expanded size are bounded.
    """
    registry = {item["id"]: item for item in catalog["operators"]}
    flat_nodes, flat_edges, owners, keeps = [], [], {}, []
    serial = 0

    def add_node(node, owner):
        if len(flat_nodes) >= 1000:
            fail("路线展开后超过 1000 个节点，请拆分工作流。", owner)
        flat_nodes.append(node)
        owners[node.id] = owner

    def visit(current, path=(), bindings=None, ancestry=(), owner=None, inherited_params=None):
        from .references import remap_params
        scoped_params = {**(inherited_params or {}), **current.params}
        nonlocal serial
        if len(path) > 6:
            fail("路线嵌套最多支持 6 层。", owner)
        nodes = {n.id: n for n in current.nodes}
        if len(nodes) != len(current.nodes):
            fail("路线节点 ID 重复。", owner)
        bindings = bindings or {}
        incoming = {n.id: {} for n in current.nodes}
        seen_edges = set()
        for edge in current.edges:
            if edge.id in seen_edges or edge.source not in nodes or edge.target not in nodes:
                fail("路线包含重复或无效连线。", owner)
            seen_edges.add(edge.id)
            port = int(edge.targetHandle[3:])
            if port in incoming[edge.target] or nodes[edge.target].kind == "source":
                fail("路线输入重复连接或数据源被作为连线目标。", owner or edge.target)
            incoming[edge.target][port] = edge
        endpoints, active, local_names = {}, set(), {}
        for node in current.nodes:
            if node.kind == "route":
                continue
            if node.id in bindings:
                endpoints[node.id] = [bindings[node.id]]
                continue
            copied = node.model_copy(deep=True)
            copied.context_params = {**scoped_params, **copied.context_params}
            if path:
                digest = sha256("/".join((*path, node.id)).encode()).hexdigest()[:20]
                copied.id = f"r_{digest}"
                if registry.get(node.operator, {}).get("output_parameter"):
                    copied.params["output"] = copied.id
                filename = copied.params.get("filename")
                if filename:
                    # Validate rather than silently sanitize an unsafe filename.
                    if not isinstance(filename, str) or any(c in filename for c in "/\\:"):
                        fail("图片文件名不能包含目录或驱动器。", owner)
                    copied.params["filename"] = f"{copied.id}_{filename}"
            add_node(copied, owner or node.id)
            names = output_names(copied, registry)
            endpoints[node.id] = [(copied.id, "out" if len(names) == 1 else f"out-{i}") for i in range(len(names))]
            for old, new in zip(output_names(node, registry), names):
                local_names[old] = new

        def source_endpoint(node_id, handle):
            values = resolve_node(node_id)
            index = port_index(handle)
            if index >= len(values):
                fail("路线连线引用了不存在的输出端口。", owner or node_id)
            return values[index]

        def resolve_node(node_id):
            if node_id in endpoints:
                return endpoints[node_id]
            if node_id in active:
                fail("路线之间存在环路。", owner or node_id)
            active.add(node_id)
            node = nodes[node_id]
            definition = require_route(node)
            if definition.id in ancestry:
                fail("路线不能递归调用自身。", owner or node.id)
            check_interface(definition.graph, catalog)
            ports = definition.graph.interface.inputs
            if set(incoming[node_id]) != set(range(len(ports))):
                fail(f"{node.title or definition.name}需要 {len(ports)} 个输入，请连接全部端口。", owner or node.id)
            wired = {port.node_id: source_endpoint(incoming[node_id][i].source, incoming[node_id][i].sourceHandle)
                     for i, port in enumerate(ports)}
            inner = visit(definition.graph, (*path, node_id), wired, (*ancestry, definition.id), owner or node.id, scoped_params)
            values = [inner(port.node_id, port.handle) for port in definition.graph.interface.outputs]
            endpoints[node_id] = values
            for alias, endpoint in zip(output_names(node, registry), values):
                produced = next(n for n in flat_nodes if n.id == endpoint[0])
                local_names[alias] = output_names(produced, registry)[port_index(endpoint[1])]
            active.remove(node_id)
            return values

        for node in current.nodes:
            resolve_node(node.id)
        for name, endpoint in (bindings or {}).items():
            produced = next(n for n in flat_nodes if n.id == endpoint[0])
            local_names[name] = output_names(produced, registry)[port_index(endpoint[1])]
        for node in current.nodes:
            if node.kind != "operator":
                continue
            target_id = node.id if not path else "r_" + sha256("/".join((*path, node.id)).encode()).hexdigest()[:20]
            copied = next(n for n in flat_nodes if n.id == target_id)
            copied.params = remap_params(copied.operator, copied.params, local_names)
        for edge in current.edges:
            if nodes[edge.target].kind == "route":
                continue
            source_id, handle = source_endpoint(edge.source, edge.sourceHandle)
            # Report nodes have no outputs; their deterministic ID is independent.
            target_id = edge.target if not path else "r_" + sha256("/".join((*path, edge.target)).encode()).hexdigest()[:20]
            serial += 1
            if serial > 5000:
                fail("路线展开后超过 5000 条连接。", owner)
            flat_edges.append(GraphEdge(id=f"expanded_{serial}", source=source_id, target=target_id,
                                        sourceHandle=handle, targetHandle=edge.targetHandle))
        for name in current.memory.get("keep", []):
            if name not in local_names:
                # A placeholder source may have been requested as a retained value.
                source = bindings.get(name)
                if source:
                    produced = next(n for n in flat_nodes if n.id == source[0])
                    local_names[name] = output_names(produced, registry)[port_index(source[1])]
                else:
                    fail(f"保留数据 {name!r} 不存在。", owner)
            keeps.append(local_names[name])
        return source_endpoint

    visit(graph)
    result = graph.model_copy(deep=True)
    result.nodes, result.edges, result.interface = flat_nodes, flat_edges, None
    result.memory = {**result.memory, "keep": list(dict.fromkeys(keeps))}
    return result, owners


class RouteLibrary:
    def __init__(self, directory, catalog, root, catalog_for=None):
        self.directory, self.catalog, self.root = Path(directory), catalog, root
        self.catalog_for = catalog_for or (lambda graph: self.catalog)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.directory / ".library.lock")
        self.saved, self.registered = {}, {}
        self.revision = None
        with self.lock:
            self._reload(force=True)

    def _reload(self, force=False):
        revision = self.directory / "revision.json"
        stamp = revision.read_text(encoding="utf-8") if revision.exists() else ""
        if not force and stamp == self.revision:
            return
        saved, registered = {}, {}
        # Scan on startup or after a writer changes the revision; ordinary reads
        # check one tiny revision file, without rescanning operator modules.
        for path in self.directory.glob("route_*.json"):
            try:
                item = SavedWorkflow.model_validate_json(path.read_text(encoding="utf-8"))
                saved[item.id] = item
            except (ValueError, OSError) as error:
                raise ValueError(f"无法读取保存的路线，原文件已保留：{path}") from error
        index = self.directory / "registry.json"
        if index.exists():
            try:
                registered = {item.id: item for value in json.loads(index.read_text(encoding="utf-8"))
                              if (item := RouteDefinition.model_validate(value))}
            except (ValueError, OSError, TypeError) as error:
                raise ValueError(f"路线注册表损坏，原文件已保留：{index}") from error
        self.saved, self.registered, self.revision = saved, registered, stamp

    def changed(self):
        atomic_json(self.directory / "revision.json", uuid.uuid4().hex)
        self.revision = None

    def _write(self, path, value):
        atomic_json(path, value)

    def list_saved(self):
        with self.lock:
            self._reload()
            return [{"id": item.id, "version": item.version, "name": item.graph.name, "updated_at": item.updated_at,
                     "nodes": len(item.graph.nodes), "interface": item.graph.interface.model_dump() if item.graph.interface else None,
                     "registered_version": self.registered[item.id].version if item.id in self.registered else None}
                    for item in sorted(self.saved.values(), key=lambda item: item.updated_at, reverse=True)]

    def routes(self):
        with self.lock:
            self._reload()
            return [item.model_dump(mode="json") for item in self.registered.values()]

    def get(self, key):
        with self.lock:
            self._reload()
            if key not in self.saved:
                raise KeyError("找不到已保存的路线。")
            return self.saved[key].model_dump(mode="json")

    def save(self, payload):
        graph = prepare_interface(payload.graph, self.catalog_for(payload.graph), self.root)
        with self.lock:
            self._reload(force=True)
            key = payload.id or "route_" + uuid.uuid4().hex[:12]
            previous = self.saved.get(key)
            if payload.id and previous is None:
                raise KeyError("原路线已不存在，请另存为新路线。")
            if previous and payload.expected_version != previous.version:
                fail("路线已在其他页面更新，请重新打开或另存为，避免覆盖。")
            item = SavedWorkflow(id=key, version=previous.version + 1 if previous else 1,
                                 updated_at=datetime.now(timezone.utc).isoformat(), graph=graph)
            self._write(self.directory / f"{key}.json", item.model_dump(mode="json"))
            self.saved[key] = item
            self.changed()
            return item.model_dump(mode="json")

    def register(self, keys):
        from .graph import compile_graph
        with self.lock:
            self._reload(force=True)
            additions = {}
            for key in dict.fromkeys(keys):
                if key not in self.saved:
                    raise KeyError("找不到待注册的路线。")
                item = self.saved[key]
                catalog = self.catalog_for(item.graph)
                check_interface(item.graph, catalog)
                # Original files can be missing on another machine. Registration
                # validates the graph using harmless virtual source paths.
                checked = item.graph.model_copy(deep=True)
                from src.reader import primary_ext
                for node in checked.nodes:
                    if node.kind == "source" and node.source is not None:
                        # Preserve the declared reader contract (e.g. VCF
                        # genotype metadata); only replace the file location.
                        node.source.path = "route-input" + primary_ext(Path(node.source.path))
                compile_graph(checked, catalog, self.root)
                additions[key] = RouteDefinition(id=key, version=item.version, name=item.graph.name, graph=item.graph)
            updated = {**self.registered, **additions}
            self._write(self.directory / "registry.json", [item.model_dump(mode="json") for item in updated.values()])
            self.registered = updated
            state = self.library_state()
            state["disabled"] = [key for key in state["disabled"] if key not in additions]
            self._write(self.directory / "library_state.json", state)
            self.changed()
            return self.routes()

    def library_state(self):
        with self.lock:
            path = self.directory / "library_state.json"
            return (LibraryState.model_validate_json(path.read_text(encoding="utf-8"))
                    if path.exists() else LibraryState()).model_dump()

    def manage_item(self, key, action):
        with self.lock:
            self._reload(force=True)
            atomic = {item["id"] for item in self.catalog["operators"]}
            if key not in atomic and key not in self.registered:
                raise KeyError("算子已不存在，请刷新算子库。")
            state = self.library_state()
            disabled, hidden = set(state["disabled"]), set(state["hidden"])
            if action == "disable":
                disabled.add(key)
            elif action == "enable":
                disabled.discard(key)
            elif action == "restore":
                hidden.discard(key); disabled.discard(key)
            elif action == "delete":
                disabled.discard(key)
                if key in self.registered:
                    self.registered.pop(key)
                    self._write(self.directory / "registry.json", [r.model_dump(mode="json") for r in self.registered.values()])
                else:
                    hidden.add(key)
            else:
                fail("不支持的算子库操作。")
            self._write(self.directory / "library_state.json", {"disabled": sorted(disabled), "hidden": sorted(hidden)})
            self.changed()
            return {"routes": self.routes(), "state": self.library_state()}

    def install_builtins(self):
        """Seed shipped routes once. Removal/disable and user edits survive boots."""
        bundle = json.loads(Path(__file__).with_name("builtin_routes.json").read_text(encoding="utf-8"))
        with self.lock:
            self._reload(force=True)
            receipt = self.directory / "builtins_installed.json"
            installed = set(json.loads(receipt.read_text(encoding="utf-8"))) if receipt.exists() else set()
            pending = [RouteDefinition.model_validate(value) for value in bundle["routes"] if value["id"] not in installed]
            if not pending:
                return
            for item in pending:
                # Never overwrite an existing user-edited graph with a template.
                if item.id not in self.saved and item.id not in self.registered:
                    check_interface(item.graph, self.catalog)
                    from .graph import compile_graph
                    compile_graph(item.graph, self.catalog, self.root)
                    saved = SavedWorkflow(id=item.id, version=item.version, graph=item.graph,
                                          updated_at=datetime.now(timezone.utc).isoformat())
                    self._write(self.directory / f"{item.id}.json", saved.model_dump(mode="json"))
                    self.saved[item.id], self.registered[item.id] = saved, item
                installed.add(item.id)
            self._write(self.directory / "registry.json", [r.model_dump(mode="json") for r in self.registered.values()])
            self._write(receipt, sorted(installed))
            self.changed()

    def save_workspace(self, workspace: Workspace):
        ids = [document.id for document in workspace.documents]
        if len(set(ids)) != len(ids) or workspace.active_id not in ids:
            fail("页面 ID 重复或活动页面不存在。")
        with self.lock:
            self._write(self.directory / "workspace.json", workspace.model_dump(mode="json"))

    def load_workspace(self):
        try:
            value = Workspace.model_validate_json((self.directory / "workspace.json").read_text(encoding="utf-8"))
            return value.model_dump(mode="json")
        except FileNotFoundError:
            return None
        except ValueError as exc:
            fail("Workspace is invalid or uses an older graph protocol. Close Studio and run biopipe migrate; the file has been preserved. " + str(exc))
