"""Bounded, explainable placement of a workflow's atomic top-level nodes.

This planner never reads file payloads or runs scientific implementations. It
uses catalog capabilities, dependency state, stat sizes and frozen host pools.
It is a transfer-cost heuristic, not a claim of globally optimal scheduling.
"""
from copy import deepcopy
import heapq
from pathlib import Path, PurePosixPath

from biopipe.file_formats import primary_ext, uncompressed_path
from biopipe.pins import identity, released_replacements
from .graph import GraphError
from .routes import output_names

LOCAL = {"kind": "local"}
ACTIVE = {"queued", "preparing", "uploading", "running", "waiting_connection"}


def target(value=None):
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_none=True)
    value = value or LOCAL
    if not isinstance(value, dict) or value.get("kind", "local") not in ("local", "ssh"):
        raise GraphError("Invalid execution environment")
    if value.get("kind", "local") == "local":
        return dict(LOCAL)
    key = value.get("profile_id")
    if not isinstance(key, str) or not key:
        raise GraphError("Choose a server connection")
    return {"kind": "ssh", "profile_id": key}


def target_key(value):
    value = target(value)
    return value.get("profile_id", "local")


def settings(graph):
    result = deepcopy(graph.runtime.get("execution") or {})
    if not isinstance(result, dict) or result.get("mode", "manual") not in ("manual", "auto"):
        raise GraphError("Execution mode must be manual or auto")
    result.setdefault("mode", "manual")
    result.update(target(result))
    if 'eligible_targets' in result:
        if not isinstance(result['eligible_targets'], list):
            raise GraphError('eligible_targets must be a list')
        result['eligible_targets'] = [target(value) for value in result['eligible_targets']]
    for key in ("node_targets", "file_locations"):
        if not isinstance(result.get(key, {}), dict):
            raise GraphError(f"{key} must be an object")
        result.setdefault(key, {})
        if any(not isinstance(name, str) or not (isinstance(value, dict) or hasattr(value, 'model_dump'))
               for name, value in result[key].items()):
            raise GraphError(f'{key} must map string names to execution environments')
        result[key] = {name: target(value) for name, value in result[key].items()}
    if "max_parallel_tasks" in result and (type(result["max_parallel_tasks"]) is not int or result["max_parallel_tasks"] < 1):
        raise GraphError("Parallel task count must be a positive integer")
    ids = {node.id for node in graph.nodes}
    if set(result["node_targets"]) - ids:
        raise GraphError("Execution settings reference missing nodes")
    return result


def source_location(node, config):
    return target(node.source.location if node.source and node.source.location else config)


def ordered_nodes(graph):
    nodes = {node.id: node for node in graph.nodes}
    if len(nodes) != len(graph.nodes):
        raise GraphError("Duplicate node ID")
    ordinal = {node.id: i for i, node in enumerate(graph.nodes)}
    outgoing, incoming = {key: [] for key in nodes}, {key: [] for key in nodes}
    for edge in graph.edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise GraphError("Connection references a missing node")
        outgoing[edge.source].append(edge.target)
        incoming[edge.target].append(edge.source)
    degree = {key: len(values) for key, values in incoming.items()}
    queue = [(ordinal[key], key) for key in nodes if not degree[key]]
    heapq.heapify(queue); order = []
    while queue:
        _, key = heapq.heappop(queue); order.append(key)
        for child in outgoing[key]:
            degree[child] -= 1
            if not degree[child]:
                heapq.heappush(queue, (ordinal[child], child))
    if len(order) != len(nodes):
        raise GraphError("Workflow contains a cycle")
    return nodes, order, incoming, outgoing


def operator_nodes(node):
    if node.kind == "operator":
        yield node
    elif node.kind == "route" and node.route:
        for child in node.route.graph.nodes:
            yield from operator_nodes(child)


def descriptor_capability(spec, info, pin=None):
    name = spec['id']
    if info.get('system') not in spec.get('supported_systems', [info.get('system')]):
        return f"{name} requires {' / '.join(spec['supported_systems'])}"
    absent = [tool for tool in spec.get('resources', {}).get('external_tools', []) if not info.get('tools', {}).get(tool)]
    if absent:
        return 'Missing executable: ' + ', '.join(absent)
    states = info.get('_dependencies')
    if states is None:
        states = {item['id']: item for item in info.get('dependencies', {}).get('entries', [])}
    if states.get(name, {}).get('status') in ('failed', 'missing', 'unavailable'):
        return f'{name} dependencies are not ready'
    if pin:
        current = spec.get('implementation') or {}
        bundled = spec.get('origin') == 'bundled'
        replacement = info.get('_released_pins', {}).get((name, identity(pin)), pin)
        validated = info.get('_validated_pins')
        if validated is None:
            validated = {(key, identity(value)) for key, values in (info.get('validated_pins') or {}).items()
                         for value in values if isinstance(value, dict)}
        if ((name, identity(pin)) not in validated and
                identity(current, bundled=bundled) != identity(replacement, bundled=bundled)):
            return f'{name} pinned implementation is unavailable'
    return None


def capability(node, info):
    operators = info.get('_operators')
    if operators is None:
        operators = {item['id']: item for item in info['catalog']['operators']}
    requirements = info.get('_requirements', {}).get(node.id)
    if requirements is None:
        requirements = [(item, None) for item in operator_nodes(node)]
    for item, pin in requirements:
        spec = operators.get(item.operator)
        if spec is None:
            return f"{item.operator} is not installed"
        failure = descriptor_capability(spec, info, pin)
        if failure:
            return failure
    return None


def _metadata(graph, infos, stat_file, warnings):
    """Collect immutable file facts and used declarations once, outside sweeps.

    References are implicit transfer edges. A route owns all its nested
    operator references; its source nodes are interface placeholders, not
    original files that will be read again by the route.
    """
    operators, readers = {}, {}
    for info in infos.values():
        for kind, collection in (('operators', operators), ('readers', readers)):
            for spec in info['catalog'].get(kind, []):
                collection.setdefault(spec['id'], []).append(spec)
    schemas = {}
    for name, variants in {**operators, **readers}.items():
        schemas[name] = {key for spec in variants
                         for key, field in spec.get('parameters_schema', {}).get('properties', {}).items()
                         if field.get('x-biopipe-path')}
    reader_by_ext = {}
    for name, variants in readers.items():
        for extension in {ext for spec in variants for ext in spec.get('extensions', [])}:
            reader_by_ext.setdefault(extension.lower(), []).append(name)
    cached_stats = {}

    def size(location, path, base, *, optional=False, label='input'):
        key = (target_key(location), path, base)
        if key not in cached_stats:
            try:
                value = stat_file(location, path, base) if stat_file else None
                if value is not None and (type(value) is not int or value < 0):
                    raise ValueError('File stat must return nonnegative bytes')
                cached_stats[key] = value, None
            except (OSError, ValueError, KeyError) as exc:
                cached_stats[key] = None, str(exc)
        value, error = cached_stats[key]
        if error and not optional:
            warning = f'{label}: input size unavailable ({error})'
            if warning not in warning_keys:
                warnings.append(warning); warning_keys.add(warning)
        return value

    warning_keys = set()
    requirements, references, source_references, source_readers, source_sizes = {}, {}, {}, {}, {}

    def walk(part, inherited, prefix=(), owner=None, parent_pins=None):
        config = settings(part)
        original_config = config if part.runtime.get('execution') else inherited
        pins = {**(parent_pins or {}), **part.plugin_lock}
        valid_locations = set()

        def reference(node, field, value, where, base, collection):
            if not isinstance(value, str) or not value:
                raise GraphError(f'{field} must reference a nonempty file path', owner or node.id)
            if target_key(where) not in infos:
                raise GraphError(f'Reference environment is unavailable: {target_key(where)}', owner or node.id)
            label = '.'.join((*prefix, field))
            collection.append({'source': owner or node.id, 'parameter': label,
                               'path': value, 'base_dir': base, 'from': target(where),
                               'estimated_bytes': size(where, value, base, label=label)})

        for node in part.nodes:
            atomic = owner or node.id
            if node.kind == 'operator':
                requirements.setdefault(atomic, []).append((node, pins.get(node.operator)))
                refs = references.setdefault(atomic, [])
                for name in schemas.get(node.operator, set()):
                    field = f'{node.id}.params.{name}'
                    value = node.params.get(name)
                    if value is not None and value != '':
                        valid_locations.add(field)
                        where = config['file_locations'].get(field, target(original_config))
                        reference(node, field, value, where, part.base_dir, refs)
            elif node.kind == 'source' and node.source:
                candidates = reader_by_ext.get(primary_ext(node.source.path), [])
                fields = {name for reader in candidates for name in schemas.get(reader, set())}
                if owner:
                    valid_locations.update(f'{node.id}.source.args.{name}' for name in fields
                                           if node.source.args.get(name) is not None and node.source.args[name] != '')
                    continue
                location = source_location(node, original_config)
                if target_key(location) not in infos:
                    raise GraphError(f'Input environment is unavailable: {target_key(location)}', node.id)
                source_sizes[node.id] = size(location, node.source.path, part.base_dir, label=node.title or node.id) if node.source.path else None
                origin_readers = {spec['id'] for spec in infos[target_key(location)]['catalog'].get('readers', [])
                                  if primary_ext(node.source.path) in spec.get('extensions', [])}
                if origin_readers:
                    candidates = [name for name in candidates if name in origin_readers]
                path_type = Path if location['kind'] == 'local' else PurePosixPath
                source_base = str((path_type(part.base_dir) / node.source.path).parent)
                # Ambiguous formats (e.g. BED/PLINK) are resolved from sibling
                # metadata only. Without a stat callback, require all possible
                # readers conservatively rather than guessing a file format.
                selected = []
                for name in candidates:
                    descriptor = readers[name][0]
                    matches = True
                    if len(candidates) > 1 and stat_file:
                        primary = uncompressed_path(path_type(node.source.path))
                        sibling = lambda ext: primary.with_suffix(ext).name
                        matches = all(size(location, sibling(ext), source_base, optional=True) is not None
                                      for ext in descriptor.get('requires_siblings', []))
                        matches &= not any(size(location, sibling(ext), source_base, optional=True) is not None
                                           for ext in descriptor.get('excludes_siblings', []))
                    if matches:
                        selected.append((name, pins.get(name)))
                source_readers[node.id] = selected
                refs = source_references.setdefault(node.id, [])
                for name in {field for reader, _ in selected for field in schemas.get(reader, set())}:
                    field = f'{node.id}.source.args.{name}'
                    value = node.source.args.get(name)
                    if value is None or value == '':
                        continue
                    valid_locations.add(field)
                    marked = field in config['file_locations']
                    where = config['file_locations'].get(field, location)
                    reference(node, field, value, where, part.base_dir if marked else source_base, refs)
            elif node.kind == 'route' and node.route:
                walk(node.route.graph, original_config, (*prefix, node.id), atomic, pins)
        unknown = set(config['file_locations']) - valid_locations
        if unknown:
            raise GraphError('file_locations must name existing path parameters: ' + ', '.join(sorted(unknown)), owner)

    walk(graph, settings(graph))
    return requirements, references, source_references, source_readers, source_sizes


def make_plan(graph, infos, *, stat_file=None):
    config = settings(graph)
    nodes, order, incoming, outgoing = ordered_nodes(graph)
    default = target_key(config)
    info_by_key = {target_key(info["target"]): dict(info) for info in infos}
    allowed = {target_key(t) for t in config.get("eligible_targets", [])} or set(info_by_key)
    if config["mode"] == "manual":
        allowed |= {target_key(t) for t in config["node_targets"].values()} | {default}
    assigned, choices, reasons, sizes, warnings = {}, {}, {}, {}, []
    requirements, references, source_references, source_readers, source_sizes = _metadata(graph, info_by_key, stat_file, warnings)
    for info in info_by_key.values():
        info['_operators'] = {spec['id']: spec for spec in info['catalog']['operators']}
        info['_readers'] = {spec['id']: spec for spec in info['catalog'].get('readers', [])}
        info['_dependencies'] = {item['id']: item for item in info.get('dependencies', {}).get('entries', [])}
        info['_requirements'] = requirements
        # These are original pins explicitly accepted by the destination's
        # PluginManager.snapshot, not unverified aliases supplied by a graph.
        info['_validated_pins'] = {(name, identity(pin))
                                   for name, pins in (info.get('validated_pins') or {}).items()
                                   for pin in pins if isinstance(pin, dict)}
        info['_released_pins'] = released_replacements(graph, {**info['_operators'], **info['_readers']})

    def reader_capability(source_id, info):
        readers = source_readers.get(source_id, [])
        if not readers:
            return f'No Reader is installed for {nodes[source_id].source.path}'
        for name, pin in readers:
            spec = info['_readers'].get(name)
            if spec is None:
                return f'{name} is not installed'
            failure = descriptor_capability(spec, info, pin)
            if failure:
                return failure
        return None

    for key in order:
        node = nodes[key]
        if node.kind == "source":
            location = source_location(node, config)
            if target_key(location) not in info_by_key:
                raise GraphError(f"Input environment is unavailable: {target_key(location)}", key)
            assigned[key] = target_key(location)
            sizes[key] = source_sizes.get(key)
            continue
        candidates, failures = [], []
        for name, info in info_by_key.items():
            if name not in allowed:
                continue
            failure = capability(node, info)
            if not failure:
                for source_id in incoming[key]:
                    if nodes[source_id].kind == 'source':
                        failure = reader_capability(source_id, info)
                        if failure:
                            break
            if failure:
                failures.append(f"{info.get('name', name)}: {failure}")
            else:
                candidates.append(name)
        desired = target_key(config["node_targets"].get(key, config))
        if config["mode"] == "manual":
            if desired not in candidates:
                raise GraphError(f"{node.title or node.operator or key}: selected environment is unavailable. " + "; ".join(failures), key)
            candidates = [desired]
        if not candidates:
            raise GraphError(f"{node.title or node.operator or key}: no eligible environment. " + "; ".join(failures), key)
        choices[key] = candidates
        # Unknown output size remains unknown; it is never treated as a free edge.
        known = [sizes[parent] for parent in incoming[key] if sizes.get(parent) is not None]
        sizes[key] = sum(known) if known else None
        assigned[key] = desired if desired in candidates else candidates[0]

    def weight(value):
        return float(value if value is not None else 64 * 1024**2)

    def reference_cost(values):
        total = sum(weight(item['estimated_bytes']) for item in values)
        local = {}
        for item in values:
            location = target_key(item['from'])
            local[location] = local.get(location, 0.) + weight(item['estimated_bytes'])
        return {name: total - local.get(name, 0.) for name in info_by_key}

    reference_costs = {key: reference_cost(values) for key, values in references.items()}
    source_reference_costs = {key: reference_cost(values) for key, values in source_references.items()}
    for key in choices:
        costs = reference_costs.setdefault(key, dict.fromkeys(info_by_key, 0.))
        for parent in incoming[key]:
            for name, value in source_reference_costs.get(parent, {}).items():
                costs[name] += value

    def edge_cost(source, destination):
        return weight(sizes.get(source)) if assigned[source] != destination else 0.

    def cost(key, destination):
        info = info_by_key[destination]
        resources = info.get("resources", {})
        # Queue pressure is deliberately modest relative to moving a large data
        # set. No unstable free-memory polling or payload-size guesses are used.
        queue_cost = (resources.get("queued_jobs", 0) + resources.get("active_jobs", 0)) * 8 * 1024**2
        transfer = sum(edge_cost(parent, destination) for parent in incoming[key])
        transfer += sum(weight(sizes.get(key)) for child in outgoing[key] if assigned.get(child) != destination)
        return transfer + reference_costs[key][destination] + queue_cost

    if config["mode"] == "auto":
        # Fixed four coordinate sweeps: O((V+E)*hosts), independent of 2**V.
        # Reverse sweeps pull portable preprocessing towards Linux-only tools.
        for sequence in (list(reversed(order)), order, list(reversed(order)), order):
            for key in sequence:
                if key not in choices:
                    continue
                assigned[key] = min(choices[key], key=lambda dest: (cost(key, dest), dest != default, dest))

    units, owner = [], {}
    for key in order:
        if nodes[key].kind == "source":
            continue
        dest = assigned[key]
        if not units or target_key(units[-1]["target"]) != dest:
            units.append({"id": f"stage_{len(units)+1}", "node_ids": [], "target": target(info_by_key[dest]["target"]),
                          "reason": "Manual selection" if config["mode"] == "manual" else "Compatible dependencies; input locality and queue cost",
                          "estimated_bytes": 0, "depends_on": []})
        unit = units[-1]; unit["node_ids"].append(key); owner[key] = unit["id"]
        unit["estimated_bytes"] += sizes.get(key) or 0
    transfers = []
    units_by_id = {unit['id']: unit for unit in units}
    for edge in graph.edges:
        if edge.target not in owner:
            raise GraphError("Input nodes cannot have incoming connections", edge.target)
        unit = units_by_id[owner[edge.target]]
        if edge.source in owner and owner[edge.source] != owner[edge.target]:
            unit["depends_on"].append(owner[edge.source])
        if assigned[edge.source] != assigned[edge.target]:
            source_target = source_location(nodes[edge.source], config) if nodes[edge.source].kind == "source" else info_by_key[assigned[edge.source]]["target"]
            transfers.append({"source": edge.source, "target": edge.target, "from": target(source_target),
                              "to": unit["target"], "estimated_bytes": sizes.get(edge.source)})
    for key in choices:
        refs = [*references.get(key, [])]
        for parent in incoming[key]:
            refs.extend(source_references.get(parent, []))
        for item in refs:
            if target_key(item['from']) != assigned[key]:
                transfers.append({**item, 'target': key, 'to': units_by_id[owner[key]]['target']})
    for unit in units:
        unit["depends_on"] = sorted(set(unit["depends_on"]))
    if not units:
        raise GraphError("Add at least one analysis operator")
    return {"mode": config["mode"], "units": units, "transfers": transfers, "warnings": warnings,
            "algorithm": "bounded-locality-v1", "optimality": "heuristic"}
