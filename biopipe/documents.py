"""Authoritative canvas sessions, transactional edits and semantic context.

Transient presence has its own revision. All graph writes (UI or agent) use a
compare-and-swap document revision and the same bounded undo history.
"""
from copy import deepcopy
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

from src.web.models import Graph, Workspace
from src.web.storage import FileLock, atomic_json
from src.web.contracts import analyze_graph


class CommandError(ValueError):
    def __init__(self, code, message, status=422, details=None):
        super().__init__(message)
        self.code, self.status, self.details = code, status, details


def now():
    return datetime.now(timezone.utc).isoformat()


def layout(graph):
    """Fill only absent positions with a deterministic, branched DAG layout."""
    graph = deepcopy(graph)
    nodes = {n["id"]: n for n in graph.get("nodes", [])}
    levels = {key: 0 for key in nodes}
    incoming = {key: 0 for key in nodes}
    outgoing = {key: [] for key in nodes}
    for edge in graph.get("edges", []):
        if edge["source"] in nodes and edge["target"] in nodes:
            incoming[edge["target"]] += 1
            outgoing[edge["source"]].append(edge["target"])
    ready = deque(key for key in nodes if not incoming[key])
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for target in outgoing[key]:
            levels[target] = max(levels[target], levels[key] + 1)
            incoming[target] -= 1
            if not incoming[target]:
                ready.append(target)
    if visited != len(nodes):
        raise CommandError("invalid_graph", "Graph contains a cycle")
    rows = {}
    for key, node in nodes.items():
        level = levels[key]
        row = rows.get(level, 0)
        rows[level] = row + 1
        node.setdefault("position", {"x": 60 + level * 300, "y": 80 + row * 210})
    return graph


class DocumentHub:
    def __init__(self, service):
        self.service = service
        self.directory = service.directory / "agent/sessions"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(self.directory / ".sessions.lock")

    def path(self, session):
        if not isinstance(session, str) or len(session) != 32 or any(c not in "0123456789abcdef" for c in session):
            raise CommandError("not_found", "Unknown canvas session", 404)
        return self.directory / f"{session}.json"

    def load(self, session):
        try:
            return json.loads(self.path(session).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise CommandError("not_found", "Unknown canvas session", 404)

    def save(self, state):
        atomic_json(self.path(state["id"]), state)

    def event(self, state, kind, actor, **payload):
        state["seq"] += 1
        state["events"].append({"seq": state["seq"], "time": now(), "type": kind, "actor": actor,
                                "revision": state["revision"], **payload})
        state["events"] = state["events"][-200:]

    @staticmethod
    def public(state, *, workspace=True):
        value = {key: deepcopy(state[key]) for key in ("id", "name", "revision", "ui_revision", "seq", "updated_at", "presence", "connections")}
        if workspace:
            value["workspace"] = deepcopy(state["workspace"])
        value["history"] = {key: {"undo": len(item["past"]), "redo": len(item["future"])} for key, item in state["history"].items()}
        return value

    def create(self, workspace, name="BioPipe Studio"):
        workspace = Workspace.model_validate(workspace).model_dump(mode="json")
        state = {"id": uuid.uuid4().hex, "name": str(name)[:100], "revision": 0, "ui_revision": 0,
                 "seq": 0, "events": [], "updated_at": now(), "presence": {}, "history": {}, "receipts": {},
                 "connections": {}, "workspace": workspace}
        with self.lock:
            self.save(state)
        return self.public(state)

    def list(self):
        with self.lock:
            return [self.public(json.loads(p.read_text(encoding="utf-8")), workspace=False)
                    for p in self.directory.glob("*.json")]

    def get(self, session):
        with self.lock:
            return self.public(self.load(session))

    def expect(self, state, revision):
        if revision != state["revision"]:
            raise CommandError("revision_conflict", "The canvas changed. Read the latest context before editing.", 409,
                               {"revision": state["revision"]})

    def presence(self, session, value):
        with self.lock:
            state = self.load(session)
            active = value.get("document_id")
            document = next((d for d in state["workspace"]["documents"] if d["id"] == active), None)
            if document is None:
                raise CommandError("not_found", "Presence references an unknown document", 404)
            nodes = {node["id"] for node in document["graph"]["nodes"]}
            edges = {edge["id"] for edge in document["graph"]["edges"]}
            value = {"document_id": active, "nodes": [n for n in value.get("nodes", []) if n in nodes],
                     "edges": [e for e in value.get("edges", []) if e in edges],
                     "inspected_node": value.get("inspected_node") if value.get("inspected_node") in nodes else None,
                     "focused_field": str(value.get("focused_field") or "")[:200],
                     "viewport": value.get("viewport")}
            if state["presence"] == value and (datetime.now(timezone.utc) - datetime.fromisoformat(state["updated_at"])).total_seconds() < 5:
                return self.public(state, workspace=False)
            state["updated_at"] = now()
            if state["presence"] != value:
                state["presence"] = value
                state["ui_revision"] += 1
                self.event(state, "selection.changed", "user")
            self.save(state)
            return self.public(state, workspace=False)

    def _commit(self, state, workspace, actor, label, record=True):
        previous = {doc["id"]: doc for doc in state["workspace"]["documents"]}
        changed = set(previous) != {doc["id"] for doc in workspace["documents"]} or any(
            doc["id"] not in previous or previous[doc["id"]]["graph"] != doc["graph"] for doc in workspace["documents"])
        if record:
            for doc in workspace["documents"]:
                old = previous.get(doc["id"])
                if old and old["graph"] != doc["graph"]:
                    history = state["history"].setdefault(doc["id"], {"past": [], "future": []})
                    history["past"] = [*history["past"][-29:], {"graph": deepcopy(old["graph"]), "actor": actor, "label": label}]
                    history["future"] = []
        state["workspace"] = workspace
        if changed:
            state["revision"] += 1
        else:
            state["ui_revision"] += 1
        state["updated_at"] = now()
        self.event(state, "graph.changed" if changed else "view.changed", actor, label=label)
        # Keep the legacy startup workspace usable by desktop and older builds.
        self.service.routes.save_workspace(Workspace.model_validate(workspace))
        self.save(state)
        return self.public(state)

    def sync(self, session, workspace, revision):
        workspace = Workspace.model_validate(workspace).model_dump(mode="json")
        with self.lock:
            state = self.load(session)
            self.expect(state, revision)
            if state["workspace"] == workspace:
                return self.public(state)
            return self._commit(state, workspace, "user", "Edit canvas")

    def context(self, session, scope="selection", actor=None):
        if scope not in ("selection", "document"):
            raise CommandError("invalid_scope", "Scope must be selection or document")
        with self.lock:
            state = self.load(session)
            if actor:
                state["connections"][actor] = now()
                self.save(state)
            presence = state["presence"]
            active = presence.get("document_id") or state["workspace"]["active_id"]
            doc = next(d for d in state["workspace"]["documents"] if d["id"] == active)
            graph = doc["graph"]
            selected = set(presence.get("nodes", []))
            selected_edges = set(presence.get("edges", []))
            for edge in graph["edges"]:
                if edge["id"] in selected_edges:
                    selected.update((edge["source"], edge["target"]))
            included = set(selected)
            for edge in graph["edges"]:
                if edge["source"] in selected or edge["target"] in selected:
                    included.update((edge["source"], edge["target"]))
            if scope == "document":
                included = {n["id"] for n in graph["nodes"]}
            model = Graph.model_validate(graph)
            try:
                analysis = analyze_graph(model, self.service.plugins.catalog_for(model, self.service.base_catalog), self.service.root)
                analysis = {**analysis, "nodes": {k:v for k,v in analysis["nodes"].items() if k in included},
                            "edges": [e for e in analysis["edges"] if e["source"] in included and e["target"] in included]}
            except ValueError as error:
                analysis = {"error": str(error)}
            return {"protocol_version": 1, "session_id": session, "document_id": active,
                    "revision": state["revision"], "ui_revision": state["ui_revision"], "updated_at": state["updated_at"],
                    "selection": presence, "name": graph["name"], "scope": scope,
                    "nodes": [deepcopy(n) for n in graph["nodes"] if n["id"] in included],
                    "edges": [deepcopy(e) for e in graph["edges"] if e["source"] in included and e["target"] in included],
                    "memory": graph["memory"], "params": graph.get("params", {}),
                    "runtime": graph.get("runtime", {}), "plugin_lock": graph.get("plugin_lock", {}), "contracts": analysis,
                    "empty_selection": not bool(selected), "total_nodes": len(graph["nodes"])}

    def apply(self, session, document, revision, commands, actor="agent", request_id=None):
        if not isinstance(commands, list) or not 1 <= len(commands) <= 200:
            raise CommandError("invalid_commands", "Provide 1–200 edit commands")
        with self.lock:
            state = self.load(session)
            if request_id and request_id in state["receipts"]:
                receipt = state["receipts"][request_id]
                if receipt["commands"] != commands or receipt["document"] != document or receipt["actor"] != actor:
                    raise CommandError("idempotency_conflict", "Request ID already used for different edits", 409)
                return self.public(state)
            self.expect(state, revision)
            workspace = deepcopy(state["workspace"])
            doc = next((d for d in workspace["documents"] if d["id"] == document), None)
            if doc is None:
                raise CommandError("not_found", "Unknown document", 404)
            graph = doc["graph"]
            for command in commands:
                op = command.get("op")
                if op == "add_node":
                    graph["nodes"].append(deepcopy(command["node"]))
                elif op in ("update_node", "remove_node"):
                    node = next((n for n in graph["nodes"] if n["id"] == command.get("id")), None)
                    if node is None:
                        raise CommandError("not_found", "Unknown node", 404)
                    if op == "remove_node":
                        graph["nodes"].remove(node)
                        graph["edges"] = [e for e in graph["edges"] if node["id"] not in (e["source"], e["target"])]
                    else:
                        patch = deepcopy(command["patch"])
                        if "id" in patch or "kind" in patch:
                            raise CommandError("invalid_patch", "Node ID and kind are immutable")
                        node.update(patch)
                elif op == "connect":
                    graph["edges"].append(deepcopy(command["edge"]))
                elif op == "disconnect":
                    if not any(e["id"] == command.get("id") for e in graph["edges"]):
                        raise CommandError("not_found", "Unknown edge", 404)
                    graph["edges"] = [e for e in graph["edges"] if e["id"] != command["id"]]
                elif op == "configure":
                    patch = command["patch"]
                    if set(patch) - {"name", "memory", "base_dir", "params", "runtime", "manifest_extra"}:
                        raise CommandError("invalid_patch", "configure accepts name, memory, base_dir, params, runtime and manifest_extra")
                    graph.update(deepcopy(patch))
                else:
                    raise CommandError("invalid_command", f"Unknown edit operation: {op}")
            model = Graph.model_validate(layout(graph))
            model = self.service.plugins.pin(model)
            catalog = self.service.plugins.catalog_for(model, self.service.base_catalog)
            analysis = analyze_graph(model, catalog, self.service.root)
            incompatible = [e for e in analysis["edges"] if e["status"] == "incompatible"]
            if incompatible:
                raise CommandError("incompatible_contract", "Edit creates incompatible connections", details=incompatible)
            doc["graph"] = model.model_dump(mode="json")
            state["connections"][actor] = now()
            if request_id:
                state["receipts"][request_id] = {"commands": commands, "document": document, "actor": actor}
                state["receipts"] = dict(list(state["receipts"].items())[-100:])
            return self._commit(state, workspace, actor, "Agent edit")

    def open(self, session, graph, revision, actor="agent"):
        model = self.service.plugins.pin(Graph.model_validate(layout(graph)))
        analyze_graph(model, self.service.plugins.catalog_for(model, self.service.base_catalog), self.service.root)
        with self.lock:
            state = self.load(session)
            self.expect(state, revision)
            workspace = deepcopy(state["workspace"])
            if len(workspace["documents"]) >= 20:
                raise CommandError("document_limit", "Close a tab before opening another graph")
            doc = {"id": "page_" + uuid.uuid4().hex, "graph": model.model_dump(mode="json")}
            workspace["documents"].append(doc)
            workspace["active_id"] = doc["id"]
            state["presence"] = {"document_id": doc["id"], "nodes": [], "edges": []}
            return self._commit(state, workspace, actor, "Open graph")

    def undo(self, session, document, revision, redo=False, actor="user"):
        with self.lock:
            state = self.load(session)
            self.expect(state, revision)
            workspace = deepcopy(state["workspace"])
            doc = next((d for d in workspace["documents"] if d["id"] == document), None)
            if doc is None:
                raise CommandError("not_found", "Unknown document", 404)
            history = state["history"].setdefault(document, {"past": [], "future": []})
            source, target = ("future", "past") if redo else ("past", "future")
            if not history[source]:
                raise CommandError("empty_history", "No edit to undo/redo", 409)
            history[target].append({"graph": doc["graph"], "actor": actor, "label": source})
            doc["graph"] = history[source].pop()["graph"]
            return self._commit(state, workspace, actor, "Redo" if redo else "Undo", record=False)

    def events(self, session, after):
        with self.lock:
            state = self.load(session)
            events = [event for event in state["events"] if event["seq"] > after]
            return {"seq": state["seq"], "reset": bool(state["events"] and after < state["events"][0]["seq"] - 1), "events": events}
