"""Validate a visual DAG and compile a deterministic, sequential manifest."""
import heapq
import json
import os
from pathlib import Path

import yaml

from src.task.manifest import _validate_sources, _validate_steps
from src.task.memory import MemoryConfig
from .models import Graph, GraphNode, GraphEdge, Position, Source
from .references import remap_params


class GraphError(ValueError):
    def __init__(self, message, node_id=None):
        super().__init__(message)
        self.node_id = node_id


def project_path(root, path, base="."):
    root = Path(root).resolve()
    directory = (root / base).resolve()
    raw = Path(path)
    candidate = (directory / raw).resolve()
    # Studio's profile root is normally the isolated workspace, while a
    # user-authored task may live under the source checkout. Absolute source
    # paths are explicit user intent and are allowed; relative paths remain
    # confined to the selected workspace for safety and relocatability.
    if raw.is_absolute():
        return candidate
    if not directory.is_relative_to(root) or not candidate.is_relative_to(root):
        raise GraphError("相对文件路径必须位于当前 BioPipe 项目内；外部文件请写绝对路径或通过上传添加。")
    return candidate


def _relative_or_absolute(path, directory):
    """Relativize when possible; keep absolute across Windows drives."""
    try:
        return Path(os.path.relpath(path, directory)).as_posix()
    except ValueError:
        # os.path.relpath raises on Windows when source and job live on
        # different drives.
        return Path(path).as_posix()


def relative_manifest(manifest, directory):
    """Keep executable/exported workflows relocatable alongside their data."""
    result = {**manifest, "sources": {name: dict(spec) for name, spec in manifest["sources"].items()}}
    for source in result["sources"].values():
        source["path"] = _relative_or_absolute(source["path"], directory)
    memory = dict(manifest.get("runtime", {}).get("memory", {}))
    if memory.get("cache_dir"):
        memory["cache_dir"] = _relative_or_absolute(memory["cache_dir"], directory)
    result["runtime"] = {**manifest.get("runtime", {}), "memory": memory}
    return result


def compile_graph(graph: Graph, catalog: dict, root: Path, *, require_files=False):
    if any(node.kind == "route" for node in graph.nodes):
        from .contracts import analyze_graph
        from .routes import expand_routes
        analysis = analyze_graph(graph, catalog, root)
        for edge in analysis["edges"]:
            if edge["status"] == "incompatible":
                raise GraphError("；".join(edge["reasons"]), edge["target"])
        expanded, owners = expand_routes(graph, catalog)
        try:
            return compile_graph(expanded, catalog, root, require_files=require_files)
        except GraphError as exc:
            raise GraphError(str(exc), owners.get(exc.node_id, exc.node_id)) from exc
    try:
        json.dumps(graph.model_dump(), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise GraphError("参数不能包含 NaN 或无穷大。") from exc
    registry = {operator["name"]: operator for operator in catalog["operators"]}
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise GraphError("节点 ID 重复。")
    if not nodes:
        raise GraphError("先添加数据与分析算子，再运行工作流。")
    incoming = {key: {} for key in nodes}
    outgoing = {key: [] for key in nodes}
    degree = {key: 0 for key in nodes}
    outputs, used_names = {}, set()
    for node in graph.nodes:
        if node.kind == "source":
            if node.source is None or not node.source.path:
                raise GraphError("为数据节点选择输入文件。", node.id)
            outputs[node.id] = [node.id]
        else:
            if node.operator not in registry:
                raise GraphError(f"未找到算子 {node.operator!r}；请更新算子清单。", node.id)
            spec = registry[node.operator]
            strict_parameters = spec.get("parameters_schema") and not spec.get("legacy_parameters")
            if strict_parameters:
                from biopipe_sdk.protocol import validate_parameters
                params = dict(node.params)
                params.pop("_input_names", None)
                if spec.get("output_parameter"):
                    params.pop(spec["output_parameter"], None)
                try:
                    validate_parameters(spec["parameters_schema"], params)
                except ValueError as error:
                    raise GraphError(str(error), node.id) from error
            outputs[node.id] = ([str(node.params.get("output", node.id))] if spec["output_parameter"]
                                else spec["outputs"])
            for field in ([] if strict_parameters else spec["parameters"]):
                value = node.params.get(field["key"])
                if field.get("required") and (value is None or value == "" or value == []):
                    raise GraphError(f"请填写{field['label']}。", node.id)
                if value is None:
                    continue
                kind = field["type"]
                if kind in ("number", "integer"):
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise GraphError(f"{field['label']}需要数字。", node.id)
                    if kind == "integer" and int(value) != value:
                        raise GraphError(f"{field['label']}需要整数。", node.id)
                    if ("min" in field and value < field["min"]) or ("max" in field and value > field["max"]):
                        raise GraphError(f"{field['label']}超出允许范围。", node.id)
                if kind == "list" and not isinstance(value, list):
                    raise GraphError(f"{field['label']}需要标签列表。", node.id)
                if kind == "choice" and value not in field["options"]:
                    raise GraphError(f"{field['label']}不是可选值。", node.id)
                if kind == "string" and not isinstance(value, str):
                    raise GraphError(f"{field['label']}需要文本。", node.id)
                if kind == "scalar" and (isinstance(value, bool) or not isinstance(value, (str, int, float))):
                    raise GraphError(f"{field['label']}需要文本或数值。", node.id)
                if kind == "boolean" and not isinstance(value, bool):
                    raise GraphError(f"{field['label']}需要开关值。", node.id)
                if kind == "json" and not isinstance(value, (dict, list)):
                    raise GraphError(f"{field['label']}需要 JSON 对象或列表。", node.id)
        for name in outputs[node.id]:
            if not name or name in used_names:
                raise GraphError(f"输出名称 {name!r} 重复或为空，请为它设置独立名称。", node.id)
            used_names.add(name)
    for edge in graph.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise GraphError("连线包含已不存在的节点。")
        if nodes[edge.target].kind == "source":
            raise GraphError("数据源不能作为连线的输入目标。", edge.target)
        if not outputs[edge.source]:
            raise GraphError("报告和图片节点没有可传递的 Form 输出。", edge.source)
        port = int(edge.targetHandle.split("-")[1])
        arity = registry[nodes[edge.target].operator]["inputs_arity"]
        count = nodes[edge.target].input_count if arity == "*" else arity
        if port >= count or port in incoming[edge.target]:
            raise GraphError("输入端口不存在或已有连线。", edge.target)
        if edge.sourceHandle != "out":
            if not edge.sourceHandle.startswith("out-") or not edge.sourceHandle[4:].isdigit():
                raise GraphError("输出端口格式无效。", edge.source)
            if int(edge.sourceHandle[4:]) >= len(outputs[edge.source]):
                raise GraphError("输出端口不存在。", edge.source)
        incoming[edge.target][port] = edge
        outgoing[edge.source].append(edge.target)
        degree[edge.target] += 1
    ordinal = {node.id: i for i, node in enumerate(graph.nodes)}
    queue = [(ordinal[key], key) for key, count in degree.items() if not count]
    heapq.heapify(queue)
    order = []
    while queue:
        _, key = heapq.heappop(queue)
        order.append(key)
        for target in outgoing[key]:
            degree[target] -= 1
            if not degree[target]:
                heapq.heappush(queue, (ordinal[target], target))
    if len(order) != len(nodes):
        raise GraphError("工作流存在环路，请删除回连的连线。")
    sources, steps, step_ids = {}, [], []
    for key in order:
        node = nodes[key]
        if node.kind == "source":
            source = node.source.model_dump()
            path = project_path(root, source["path"], graph.base_dir)
            if require_files and not path.is_file():
                raise GraphError(f"找不到输入文件：{node.source.path}", key)
            source["path"] = str(path)
            sources[key] = source
        else:
            arity = registry[node.operator]["inputs_arity"]
            expected = node.input_count if arity == "*" else arity
            if len(incoming[key]) != expected or (arity == "*" and expected == 0):
                raise GraphError(f"{node.title or node.operator}需要 {expected} 个输入，请连接全部端口。", key)
            inputs = []
            for _, edge in sorted(incoming[key].items()):
                index = 0 if edge.sourceHandle == "out" else int(edge.sourceHandle[4:])
                inputs.append(outputs[edge.source][index])
            params = dict(node.params)
            params.pop("_input_names", None)
            if registry[node.operator]["output_parameter"]:
                params["output"] = outputs[key][0]
            # Plot filenames must remain in their run's figures directory.
            filename = params.get("filename")
            if filename is not None and (not isinstance(filename, str) or Path(filename).name != filename or "/" in filename or "\\" in filename or ":" in filename):
                raise GraphError("图片文件名不能包含目录或驱动器。", key)
            steps.append({"name": node.operator, "inputs": inputs, "params": params,
                          **({"context_params": node.context_params} if node.context_params else {})})
            step_ids.append(key)
    if not steps:
        raise GraphError("至少添加一个分析算子。")
    memory = dict(graph.memory)
    memory.setdefault("enabled", True)
    if "cache_dir" in memory:
        memory["cache_dir"] = str(project_path(root, memory["cache_dir"], graph.base_dir))
    manifest = {**graph.manifest_extra, "name": graph.name, "sources": sources, "steps": steps,
                "params": graph.params, "runtime": {**graph.runtime, "memory": memory}}
    _validate_sources(sources)
    _validate_steps(steps)
    MemoryConfig.parse(manifest, detect_available=False)
    unknown_keep = set(memory.get("keep", [])) - used_names
    if unknown_keep:
        raise GraphError(f"保留列表引用了未知数据：{sorted(unknown_keep)}。")
    from .contracts import analyze_graph
    analysis = analyze_graph(graph, catalog, root)
    for edge in analysis["edges"]:
        if edge["status"] == "incompatible":
            raise GraphError("输入输出契约不兼容：" + "；".join(edge["reasons"]), edge["target"])
    return manifest, step_ids


def _resolve_import_base(raw, base_dir, root):
    """Return (base_dir, raw) with sources located under the project root.

    A browser cannot expose the local directory of a selected YAML file.
    Imported task YAMLs normally use paths relative to their task directory
    (``input/foo.csv``), so when the requested base does not resolve every
    source we look for the task by its YAML name, then for a unique relative
    path match under tasks/routes/examples. We never guess between multiple
    candidates.
    """
    from pathlib import Path
    import os

    root = Path(root).resolve()
    base = (root / base_dir).resolve() if not Path(base_dir).is_absolute() else Path(base_dir).resolve()
    sources = raw.get("sources") or {}
    missing = []
    for name, spec in sources.items():
        path = Path(str(spec.get("path", "")))
        if not path.is_absolute() and not (base / path).is_file():
            missing.append((name, spec, path))
        elif path.is_absolute() and not path.is_file():
            missing.append((name, spec, path))
    if not missing:
        return base_dir, raw

    # 1. Exact task/route directory named like the YAML.
    name_hint = str(raw.get("name") or "").strip()
    likely = []
    if name_hint:
        likely = [root / "tasks" / name_hint, root / "routes" / name_hint]
    for directory in likely:
        if directory.is_dir() and all(
            (directory / Path(str(spec["path"]))).is_file()
            for _, spec, _ in missing
        ):
            for _, spec, path in missing:
                # Studio shows the resolved file directly; exporting a graph
                # still relativizes it against base_dir via relative_manifest.
                spec["path"] = str((directory / path).resolve())
            return Path(os.path.relpath(directory, root)).as_posix(), raw

    # 2. Unique suffix match under the usual content roots.
    search_roots = [root / "tasks", root / "routes", root / "examples"]
    matches = {}
    for name, spec, relative in missing:
        if relative.is_absolute():
            matches[name] = [relative]
            continue
        suffix = relative.as_posix()
        found = []
        for base_root in search_roots:
            if not base_root.is_dir():
                continue
            for candidate in base_root.rglob(relative.name):
                if not candidate.is_file():
                    continue
                if candidate.as_posix().endswith("/" + suffix):
                    if "output" not in candidate.relative_to(root).parts:
                        found.append(candidate.resolve())
        found = sorted(set(found))
        if not found:
            return base_dir, raw
        if len(found) > 1:
            raise ValueError(
                f"导入的 YAML 无法唯一定位 {name!r} 的输入文件 {suffix!r}；"
                f"找到 {len(found)} 个候选。请在导入框中填写 YAML 输入相对目录，"
                f"或把 YAML 放到对应任务目录。"
            )
        matches[name] = found

    # All sources must share one base directory, otherwise the graph cannot
    # represent them with a single base_dir.
    bases = []
    for name, spec, relative in missing:
        candidate = matches[name][0]
        base_candidate = candidate
        for _ in relative.parts[:-1]:
            base_candidate = base_candidate.parent
        bases.append(base_candidate)
    unique_bases = sorted({str(path) for path in bases})
    if len(unique_bases) != 1:
        raise ValueError(
            "导入的 YAML 输入文件不在同一任务目录；请在导入框中填写正确的基准目录。"
        )
    resolved_base = Path(unique_bases[0])
    for name, spec, relative in missing:
        spec["path"] = str(matches[name][0])
    return Path(os.path.relpath(resolved_base, root)).as_posix(), raw


def import_manifest(text, base_dir, catalog, root):
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), dict) or not isinstance(raw.get("steps"), list):
        raise GraphError("任务 YAML 需要 sources 和 steps。")
    try:
        base_dir, raw = _resolve_import_base(raw, base_dir, root)
    except ValueError as exc:
        raise GraphError(str(exc)) from exc
    _validate_sources(raw["sources"])
    _validate_steps(raw["steps"])
    MemoryConfig.parse(raw, detect_available=False)
    registry = {o["name"]: o for o in catalog["operators"]}
    nodes, edges, latest, names = [], [], {}, set()
    def unique(name):
        base = "".join(c if c.isascii() and (c.isalnum() or c in "_.-") else "_" for c in name) or "data"
        if not (base[0].isalpha() or base[0] == "_"):
            base = "data_" + base
        candidate, counter = base[:60], 2
        while candidate in names:
            candidate = f"{base[:60]}_{counter}"
            counter += 1
        names.add(candidate)
        return candidate
    for i, (alias, spec) in enumerate(raw["sources"].items()):
        key = unique(alias)
        nodes.append(GraphNode(id=key, kind="source", title=alias, position=Position(x=70, y=100+i*200),
                               source=Source(**{**spec, "labels": spec.get("labels", {})})))
        latest[alias] = (key, "out")
    for i, spec in enumerate(raw["steps"]):
        name = spec["name"]
        if name not in registry:
            raise GraphError(f"未找到算子 {name!r}。")
        key = unique(f"{name}_{i+1}")
        params = dict(registry[name].get("runtime_defaults", {}))
        params.update(spec.get("params") or {})
        params.pop("_input_names", None)
        aliases = {}
        for alias, (producer, handle) in latest.items():
            node = next(n for n in nodes if n.id == producer)
            aliases[alias] = (node.id if node.kind == "source" else node.params["output"]
                             if registry[node.operator]["output_parameter"] else
                             registry[node.operator]["outputs"][int(handle[4:])])
        params = remap_params(name, params, aliases)
        for port, alias in enumerate(spec.get("inputs", [])):
            if alias not in latest:
                raise GraphError(f"步骤 {i+1} 引用了尚未生成的数据 {alias!r}。")
            producer, handle = latest[alias]
            edges.append(GraphEdge(id=f"{producer}-{key}-{port}", source=producer, target=key,
                                   sourceHandle=handle, targetHandle=f"in-{port}"))
        if registry[name]["output_parameter"]:
            alias = params.get("output", name)
            # Graph data references are version-specific, so alias overwrites
            # become distinct output names while retaining every edge's source.
            params["output"] = unique(str(alias))
            latest[alias] = (key, "out")
        else:
            for j, alias in enumerate(registry[name]["outputs"]):
                latest[alias] = (key, f"out-{j}")
        nodes.append(GraphNode(id=key, kind="operator", operator=name, title=registry[name]["title"],
                               params=params, input_count=len(spec.get("inputs", [])),
                               context_params=spec.get("context_params", {}),
                               position=Position(x=360+(i%3)*280, y=100+(i//3)*200)))
    # The CLI disables management when no memory block was supplied.
    memory = dict(raw.get("runtime", {}).get("memory", {}) or {"enabled": False})
    if memory.get("keep"):
        retained = []
        for alias in memory["keep"]:
            if alias not in latest:
                raise GraphError(f"保留列表引用了未知数据 {alias!r}。")
            producer, handle = latest[alias]
            node = next(n for n in nodes if n.id == producer)
            retained.append(node.id if node.kind == "source" else node.params["output"]
                            if registry[node.operator]["output_parameter"] else
                            registry[node.operator]["outputs"][int(handle[4:])])
        memory["keep"] = retained
    graph = Graph(name=raw.get("name", "导入的工作流"), base_dir=base_dir, nodes=nodes, edges=edges, memory=memory,
                  params=raw.get("params", {}),
                  runtime={k: v for k, v in raw.get("runtime", {}).items() if k != "memory"},
                  manifest_extra={k: v for k, v in raw.items() if k not in ("name", "sources", "steps", "runtime", "params")})
    compile_graph(graph, catalog, root)
    return graph
