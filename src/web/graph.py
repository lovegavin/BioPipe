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
    candidate = (directory / path).resolve()
    if not directory.is_relative_to(root) or not candidate.is_relative_to(root):
        raise GraphError("文件路径必须位于当前 BioPipe 项目内；外部数据文件可通过上传添加。")
    return candidate


def _relative_or_absolute(path, directory):
    try:
        return Path(os.path.relpath(path, directory)).as_posix()
    except ValueError:
        # A Windows data drive cannot be expressed relative to a job on another
        # drive. Preserve the already validated absolute input in that case.
        return Path(path).as_posix()


def relative_manifest(manifest, directory, catalog=None):
    """Keep executable/exported workflows relocatable alongside their data."""
    from copy import deepcopy
    result = deepcopy(manifest)
    if catalog:
        operators = {item['id']: item for item in catalog['operators']}
        for step in result['steps']:
            if step['name'].startswith('biopipe.script.'):
                from biopipe.script_operators import validate_script
                validate_script(step['params']['script'])
                # Script paths are named file ports; code/values are frozen data.
                schema = {}
            else:
                schema = operators[step['name']]['parameters_schema']
            for key, field in schema.get('properties', {}).items():
                if field.get('x-biopipe-path') == 'workflow' and step.get('params', {}).get(key):
                    step['params'][key] = _relative_or_absolute(step['params'][key], directory)
        from biopipe.reader_selection import candidates
        for source in result['sources'].values():
            readers = candidates(catalog['readers'], source['path'], source.get('reader'))
            if len(readers) == 1:
                for key, field in readers[0]['parameters_schema'].get('properties', {}).items():
                    if field.get('x-biopipe-path') == 'source' and source.get('args', {}).get(key):
                        source['args'][key] = _relative_or_absolute(source['args'][key], Path(source['path']).parent)
    for source in result["sources"].values():
        source["path"] = _relative_or_absolute(source["path"], directory)
    memory = dict(manifest.get("runtime", {}).get("memory", {}))
    if memory.get("cache_dir"):
        memory["cache_dir"] = _relative_or_absolute(memory["cache_dir"], directory)
    result["runtime"] = {**manifest.get("runtime", {}), "memory": memory}
    return result


def input_path(root, value, base='.', input_roots=None):
    """Apply the caller's explicit read roots, or the default workspace policy."""
    if input_roots is None:
        return project_path(root, value, base)
    candidate = (Path(root) / base / value).resolve()
    if not any(candidate.is_relative_to(Path(folder).resolve()) for folder in input_roots):
        raise GraphError('Input path is outside the configured server data roots')
    return candidate


def compile_graph(graph: Graph, catalog: dict, root: Path, *, require_files=False, input_roots=None):
    def read_path(value, base):
        return input_path(root, value, base, input_roots)
    from .parameters import freeze_graph
    if any(node.kind == "script" for node in graph.nodes):
        from biopipe.script_operators import prepare_script_graph
        graph, catalog = prepare_script_graph(graph, catalog)
    graph = freeze_graph(graph, catalog, root, input_roots=input_roots)
    if any(node.kind == "route" for node in graph.nodes):
        from .contracts import analyze_graph
        from .routes import expand_routes
        analysis = analyze_graph(graph, catalog, root, input_roots=input_roots)
        for edge in analysis["edges"]:
            if edge["status"] == "incompatible" or edge.get("format_unresolved"):
                raise GraphError("；".join(edge["reasons"]), edge["target"])
        expanded, owners = expand_routes(graph, catalog)
        try:
            return compile_graph(expanded, catalog, root, require_files=require_files, input_roots=input_roots)
        except GraphError as exc:
            raise GraphError(str(exc), owners.get(exc.node_id, exc.node_id)) from exc
    try:
        json.dumps(graph.model_dump(), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise GraphError("参数不能包含 NaN 或无穷大。") from exc
    registry = {operator["id"]: operator for operator in catalog["operators"]}
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
            from biopipe_sdk.protocol import validate_parameters
            params = {k: v for k, v in node.params.items() if k != '_input_names'}
            if spec.get("output_parameter"):
                params.pop(spec["output_parameter"], None)
            try:
                validate_parameters(spec["parameters_schema"], params)
            except ValueError as error:
                raise GraphError(str(error), node.id) from error
            outputs[node.id] = ([str(node.params.get("output", node.id))] if spec["output_parameter"]
                                else spec["outputs"])
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
            source.pop("location", None)
            if source.get('reader') is None:
                source.pop('reader', None)
            path = read_path(source["path"], graph.base_dir)
            if require_files and not path.is_file():
                raise GraphError(f"找不到输入文件：{node.source.path}", key)
            source["path"] = str(path)
            from biopipe.reader_selection import candidates
            is_exchange = key in graph.runtime.get('exchange_inputs', [])
            readers = [] if is_exchange else candidates(catalog['readers'], path, source.get('reader'), check_siblings=require_files)
            if not is_exchange and source.get('reader') and not readers:
                raise GraphError(f"Selected Reader {source['reader']} cannot read the file compression or required companions are missing", key)
            if require_files and not is_exchange and len(readers) != 1:
                raise GraphError('Choose a registered Reader for this input; its format is unknown or ambiguous', key)
            if len(readers) == 1:
                from biopipe_sdk.protocol import validate_parameters
                try:
                    source['args'] = validate_parameters(readers[0]['parameters_schema'], source['args'])
                except ValueError as error:
                    raise GraphError(str(error), key) from error
                for name, field in readers[0]['parameters_schema'].get('properties', {}).items():
                    if field.get('x-biopipe-path') == 'source' and source['args'].get(name):
                        extra = read_path(source['args'][name], str(path.parent))
                        if require_files and not extra.is_file():
                            raise GraphError(f'Missing input file: {extra}', key)
                        source['args'][name] = str(extra)
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
            params = {k: v for k, v in node.params.items() if k != '_input_names'}
            for name, field in registry[node.operator]['parameters_schema'].get('properties', {}).items():
                if field.get('x-biopipe-path') == 'workflow' and params.get(name):
                    extra = read_path(params[name], graph.base_dir)
                    if require_files and not extra.is_file():
                        raise GraphError(f'Missing input file: {extra}', key)
                    params[name] = str(extra)
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
    # UI/agent graphs already contain concrete values; external sidecar paths
    # cannot override them through arbitrary manifest metadata.
    manifest.pop("parameters_file", None)
    from src.core.errors.errors import ManifestError
    try:
        _validate_sources(sources)
        _validate_steps(steps)
        MemoryConfig.parse(manifest, detect_available=False)
    except ManifestError as error:
        raise GraphError(str(error)) from error
    unknown_keep = set(memory.get("keep", [])) - used_names
    if unknown_keep:
        raise GraphError(f"保留列表引用了未知数据：{sorted(unknown_keep)}。")
    from .contracts import analyze_graph
    analysis = analyze_graph(graph, catalog, root, input_roots=input_roots)
    for edge in analysis["edges"]:
        if edge["status"] == "incompatible" or edge.get("format_unresolved"):
            raise GraphError("输入输出契约不兼容：" + "；".join(edge["reasons"]), edge["target"])
    edge_specs = {edge.id: edge for edge in graph.edges}
    for step, node_id in zip(steps, step_ids):
        plans = [{"port": int(edge_specs[check["id"]].targetHandle[3:]), "edge_id": check["id"],
                  "plan": check["conversion_plan"]} for check in analysis["edges"]
                 if check["target"] == node_id and check.get("conversion_plan")]
        if plans:
            step["conversions"] = plans
    return manifest, step_ids


def _resolve_import_base(raw, base_dir, root, *, input_roots=None):
    """Locate task-relative inputs using metadata inside configured roots only.

    The browser does not expose a selected YAML file's directory. Prefer its
    declared base, then a named task/route, then a unique matching content
    directory. Never guess between matches or inspect paths outside the roots.
    Explicit non-root bases and missing template inputs are left intact.
    """
    root = Path(root).resolve()
    base = project_path(root, '.', base_dir)
    sources = [source for source in raw['sources'].values()
               if not source.get('location') or source['location'].get('kind') != 'ssh']
    if raw.get('runtime', {}).get('execution', {}).get('kind') == 'ssh':
        return base_dir
    paths = [(source, Path(source['path'])) for source in sources]

    def resolved(directory):
        return [input_path(root, path, str(directory), input_roots) for _, path in paths]

    original = resolved(base)  # Check containment before even stat-ing inputs.
    missing = [(source, path) for (source, path), target in zip(paths, original)
               if not target.is_file()]
    selected = base
    if missing and base == root and all(not path.is_absolute() for _, path in missing):
        name = str(raw.get('name') or '').strip()
        candidates = []
        if name and Path(name).name == name and name not in ('.', '..'):
            for folder in ('tasks', 'routes', 'examples'):
                directory = (root / folder / name).resolve()
                if directory.is_relative_to(root) and directory.is_dir():
                    if all(path.is_file() for path in resolved(directory)):
                        candidates.append(directory)
        if not candidates:
            possible = None
            for _, relative in missing:
                found = set()
                for folder in ('tasks', 'routes', 'examples'):
                    search = root / folder
                    if not search.is_dir():
                        continue
                    for candidate in search.rglob(relative.name):
                        candidate = candidate.resolve()
                        if not candidate.is_relative_to(root) or not candidate.is_file():
                            continue
                        parts = candidate.relative_to(root).parts
                        if 'output' in parts or candidate.parts[-len(relative.parts):] != relative.parts:
                            continue
                        directory = candidate
                        for _ in relative.parts:
                            directory = directory.parent
                        found.add(directory)
                possible = found if possible is None else possible & found
            candidates = sorted(directory for directory in (possible or [])
                                if all(path.is_file() for path in resolved(directory)))
        candidates = sorted(set(candidates))
        if len(candidates) > 1:
            raise GraphError('导入的 YAML 无法唯一定位输入文件；请填写明确的任务基准目录。')
        if candidates:
            selected = candidates[0]
    for (source, _), path in zip(paths, resolved(selected)):
        if path.is_file():
            source['path'] = path.as_posix()
    return selected.relative_to(root).as_posix() if selected != base else base_dir


def import_manifest(text, base_dir, catalog, root, *, input_roots=None, resolve_inputs=True):
    """Import a task; template builders preserve paths with resolve_inputs=False."""
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict) or not isinstance(raw.get("sources"), dict) or not isinstance(raw.get("steps"), list):
        raise GraphError("任务 YAML 需要 sources 和 steps。")
    if "parameters_file" in raw:
        raise GraphError("此任务 YAML 引用了独立参数文件。请导入完整路线包，或使用 CLI 在原任务目录运行；不能单独导入而丢弃参数。")
    _validate_sources(raw["sources"])
    _validate_steps(raw["steps"])
    MemoryConfig.parse(raw, detect_available=False)
    if resolve_inputs:
        base_dir = _resolve_import_base(raw, base_dir, root, input_roots=input_roots)
    registry = {o["id"]: o for o in catalog["operators"]}
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
        for field_name, field in registry[name]['parameters_schema'].get('properties', {}).items():
            if resolve_inputs and field.get('x-biopipe-path') == 'workflow' and params.get(field_name):
                params[field_name] = input_path(root, params[field_name], base_dir, input_roots).as_posix()
        params.pop('_input_names', None)
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
    compile_graph(graph, catalog, root, input_roots=input_roots)
    return graph
