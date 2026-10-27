"""Freeze defaults once; store actual values separately from graph topology."""
from copy import deepcopy
from io import BytesIO
import json
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from biopipe.file_formats import primary_ext
from .models import Graph


def _defaults(spec, values):
    schema = spec.get("parameters_schema", {})
    return {**{key: deepcopy(field["default"]) for key, field in schema.get("properties", {}).items()
               if "default" in field}, **deepcopy(values)}


def freeze_graph(graph, catalog, root, *, bound=False, depth=0):
    """Materialize declared runtime defaults without executing implementations.

    Incomplete canvases may be saved; required-value validation belongs to run.
    Nested route sources are interface placeholders and are never read.
    """
    if depth > 6:
        raise ValueError("Route nesting exceeds six levels")
    result = graph.model_copy(deep=True)
    operators = {item["id"]: item for item in catalog["operators"]}
    for node in result.nodes:
        if node.kind == "operator":
            if node.operator not in operators:
                from .graph import GraphError
                raise GraphError(f"Missing operator definition: {node.operator}", node.id)
            node.params = _defaults(operators[node.operator], node.params)
        elif node.kind == "source" and node.source and node.source.path and not bound:
            from .source_paths import source_candidates
            candidates = source_candidates(graph, catalog, root, node.source.path)
            if len(candidates) == 1:
                reader = candidates[0]
                node.source.args = _defaults(reader, node.source.args)
                if reader["id"] == "TxtReader":
                    delegate = node.source.args.get("reader", "csv")
                    choices = [item for item in catalog["readers"] if item["id"] != "TxtReader"
                               and isinstance(delegate, str) and delegate.lower() in
                               (item["id"].lower(), item["id"].removesuffix("Reader").lower())]
                    if len(choices) == 1:
                        node.source.args = _defaults(choices[0], node.source.args)
        elif node.kind == "route" and node.route:
            node.route.graph = freeze_graph(node.route.graph, catalog, root, bound=True, depth=depth + 1)
    return result


def split_graph(graph):
    """The sidecar owns values; graph.json owns structure and execution pins."""
    topology = graph.model_dump(mode="json") if isinstance(graph, Graph) else deepcopy(graph)
    values = {"format": "biopipe.graph-parameters", "schema_version": 1,
              "params": topology.pop("params", {}), "nodes": {}}
    for node in topology["nodes"]:
        if node["id"] in values["nodes"]:
            raise ValueError("Duplicate node ID in graph parameter snapshot")
        entry = {"kind": node["kind"], "operator": node.get("operator"),
                 "params": node.pop("params", {}), "context_params": node.pop("context_params", {})}
        if node.get("source") is not None:
            entry["args"] = node["source"].pop("args", {})
        if node.get("route") is not None:
            entry["route_id"] = node["route"]["id"]
            entry["route_version"] = node["route"]["version"]
            node["route"]["graph"], entry["route"] = split_graph(node["route"]["graph"])
        values["nodes"][node["id"]] = entry
    return topology, values


def restore_graph(topology, values):
    """Hydrate a strict pair, without consulting the current operator catalog."""
    graph = Graph.model_validate(topology)
    if (not isinstance(values, dict) or set(values) != {"format", "schema_version", "params", "nodes"}
            or values["format"] != "biopipe.graph-parameters" or values["schema_version"] != 1
            or not isinstance(values["params"], dict) or not isinstance(values["nodes"], dict)
            or set(values["nodes"]) != {node.id for node in graph.nodes}
            or len(graph.nodes) != len(values["nodes"]) or graph.params):
        raise ValueError("Graph parameter values do not match the saved graph")
    graph.params = deepcopy(values["params"])
    for node in graph.nodes:
        entry = values["nodes"][node.id]
        expected = {"kind", "operator", "params", "context_params"}
        if node.source is not None:
            expected.add("args")
        if node.route is not None:
            expected.update({"route_id", "route_version", "route"})
        if (not isinstance(entry, dict) or set(entry) != expected
                or entry["kind"] != node.kind or entry["operator"] != node.operator
                or not isinstance(entry["params"], dict) or not isinstance(entry["context_params"], dict)
                or node.params or node.context_params):
            raise ValueError(f"Parameter values do not match node {node.id}")
        node.params, node.context_params = deepcopy(entry["params"]), deepcopy(entry["context_params"])
        if node.source is not None:
            if not isinstance(entry["args"], dict) or node.source.args:
                raise ValueError(f"Reader parameter values do not match node {node.id}")
            node.source.args = deepcopy(entry["args"])
        if node.route is not None:
            if entry["route_id"] != node.route.id or entry["route_version"] != node.route.version:
                raise ValueError(f"Parameter values do not match nested route {node.id}")
            node.route.graph = restore_graph(node.route.graph.model_dump(mode="json"), entry["route"])
    return graph


def export_bundle(graph):
    topology, values = split_graph(graph)
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in (("graph.json", topology), ("parameters.json", values)):
            archive.writestr(name, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    return stream.getvalue()


def import_bundle(content):
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sorted(archive.namelist()) != ["graph.json", "parameters.json"]:
                raise ValueError("Workflow bundle must contain graph.json and parameters.json only")
            # Only JSON is read in memory. No archive path is extracted or executed.
            topology = json.loads(archive.read("graph.json"))
            values = json.loads(archive.read("parameters.json"))
            json.dumps([topology, values], allow_nan=False)
            return restore_graph(topology, values)
    except (BadZipFile, KeyError, UnicodeError, TypeError) as exc:
        raise ValueError(f"Invalid workflow bundle: {exc}") from exc
