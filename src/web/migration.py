"""Idempotent imports of legacy route libraries; never move/delete originals.

Only explicitly registered snapshots enter the registry. Conflicting identities
are imported under deterministic new IDs. Source JSON and previous target JSON
are retained beside a migration receipt for recovery and audit.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

from .models import Graph, RouteDefinition, SavedWorkflow, Workspace
from .profile import legacy_locations
from .routes import RouteLibrary
from .storage import FileLock, atomic_json


def signature(graph):
    """Route input files are placeholders; retain the reader/file type contract."""
    value = deepcopy(graph)
    value["base_dir"] = "."
    for node in value["nodes"]:
        if node.get("source"):
            path = node["source"]["path"]
            node["source"]["path"] = "input" + "".join(Path(path).suffixes)
        if node.get("route"):
            node["route"].pop("id", None)
            node["route"]["graph"] = signature(node["route"]["graph"])
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def migrate_profile(settings, catalog, locations=None):
    destination = Path(settings.data_dir)
    with FileLock(destination / ".migration.lock", timeout=300):
        library = RouteLibrary(destination / "workflows", catalog, settings.root)
        sources = list(legacy_locations(settings.code_root) if locations is None else locations)
        known_roots = [Path(root).resolve() for root, _ in sources]
        for old_root, old_data in sources:
            old_root, old_data = Path(old_root).resolve(), Path(old_data).resolve()
            if old_data == destination.resolve():
                continue
            key = sha256(os.path.normcase(str(old_data)).encode()).hexdigest()[:12]
            archive = destination / "migrations" / key
            if (archive / "complete.json").is_file():
                continue
            files = sorted((old_data / "workflows").glob("route_*.json"))
            files += [p for p in (old_data / "workflows/registry.json", old_data / "workflows/workspace.json",
                                 old_data / "draft.json") if p.is_file()]
            if not files:
                continue
            # Read and validate all metadata before changing the destination.
            saved, registered, workspace, draft = {}, {}, None, None
            try:
                for path in files:
                    value = read(path)
                    if path.name.startswith("route_"):
                        item = SavedWorkflow.model_validate(value)
                        saved[item.id] = item.model_dump(mode="json")
                    elif path.name == "registry.json":
                        for entry in value:
                            item = RouteDefinition.model_validate(entry)
                            registered[item.id] = item.model_dump(mode="json")
                    elif path.name == "workspace.json":
                        workspace = Workspace.model_validate(value).model_dump(mode="json")
                    else:
                        draft = Graph.model_validate(value).model_dump(mode="json")
            except (ValueError, OSError, TypeError) as error:
                raise ValueError(f"旧路线数据无法迁移，原文件已保留：{old_data}\n{error}") from error
            archive.mkdir(parents=True, exist_ok=True)
            for path in files:
                backup = archive / "source" / path.relative_to(old_data)
                if not backup.exists():
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, backup)
            warnings, copied = [], set()
            imported = Path(settings.root) / ".studio/assets/migrated" / key

            def copy_input(path, relative=None):
                if relative is None and not path.is_relative_to(old_root):
                    warnings.append(f"保留了原外部输入路径：{path}")
                    return None
                target = imported / (relative if relative is not None else path.relative_to(old_root))
                if (path, target) not in copied:
                    copied.add((path, target))
                    if path.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.copy2(path, target)
                        # PLINK readers use sidecar files sharing the same stem.
                        if path.suffix.lower() in (".bed", ".bim", ".fam"):
                            for suffix in (".bed", ".bim", ".fam"):
                                sidecar = path.with_suffix(suffix)
                                if sidecar.is_file():
                                    copy_input(sidecar, relative.with_suffix(suffix) if relative is not None else None)
                    else:
                        warnings.append(f"原输入文件不存在：{path}")
                return target.relative_to(settings.root).as_posix()

            def rebase(graph):
                graph = deepcopy(graph)
                base = Path(os.path.abspath(old_root / graph.get("base_dir", ".")))
                for node in graph["nodes"]:
                    if node.get("source"):
                        logical = Path(os.path.abspath(base / node["source"]["path"]))
                        original = logical.resolve()
                        # Windows may resolve an individual overlaid file into a
                        # package cache while its parent still resolves to real
                        # AppData. Accept only already-discovered BioPipe roots.
                        relative = (logical.relative_to(old_root) if logical.is_relative_to(old_root)
                                    and any(original.is_relative_to(root) for root in known_roots) else None)
                        moved = copy_input(original, relative)
                        if moved is not None:
                            node["source"]["path"] = moved
                    if node.get("route"):
                        node["route"]["graph"] = rebase(node["route"]["graph"])
                graph["base_dir"] = "."
                return graph

            with library.lock:
                library._reload(force=True)
                for path in library.directory.glob("*.json"):
                    backup = archive / "target-before" / path.name
                    if not backup.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, backup)
                ids, created = {}, set()
                for old_id in dict.fromkeys([*saved, *registered]):
                    original_saved, original_route = saved.get(old_id), registered.get(old_id)
                    # A registered snapshot can outlive its editable source.
                    item = deepcopy(original_saved or {"id": old_id, "version": original_route["version"],
                        "updated_at": datetime.now(timezone.utc).isoformat(), "graph": original_route["graph"]})
                    item["graph"] = rebase(item["graph"])
                    match = next((existing.id for existing in library.saved.values()
                                  if existing.version == item["version"]
                                  and (signature(existing.graph.model_dump(mode="json")) == signature(item["graph"])
                                       if original_route else existing.graph.model_dump(mode="json") == item["graph"])
                                  and (not original_route or (existing.id in library.registered
                                       and library.registered[existing.id].version == original_route["version"]
                                       and signature(library.registered[existing.id].graph.model_dump(mode="json"))
                                           == signature(original_route["graph"])))), None)
                    new_id = match or old_id
                    if not match and (new_id in library.saved or new_id in library.registered):
                        new_id = "route_" + sha256((key + old_id).encode()).hexdigest()[:12]
                    ids[old_id] = new_id
                    if match:
                        continue
                    item["id"] = new_id
                    created.add(new_id)
                    library.saved[new_id] = SavedWorkflow.model_validate(item)
                    atomic_json(library.directory / f"{new_id}.json", item)
                    if original_route:
                        route = {**original_route, "id": new_id, "graph": rebase(original_route["graph"])}
                        library.registered[new_id] = RouteDefinition.model_validate(route)
                def remap(graph):
                    for node in graph["nodes"]:
                        if node.get("route"):
                            node["route"]["id"] = ids.get(node["route"]["id"], node["route"]["id"])
                            remap(node["route"]["graph"])
                    return graph
                # Update only records created by this source, never an equivalent
                # route which already belonged to the shared destination.
                for new_id in created:
                    item = library.saved[new_id].model_dump(mode="json")
                    item["graph"] = remap(item["graph"])
                    library.saved[new_id] = SavedWorkflow.model_validate(item)
                    atomic_json(library.directory / f"{new_id}.json", item)
                    if new_id in library.registered:
                        route = library.registered[new_id].model_dump(mode="json")
                        route["graph"] = remap(route["graph"])
                        library.registered[new_id] = RouteDefinition.model_validate(route)
                atomic_json(library.directory / "registry.json", [r.model_dump(mode="json") for r in library.registered.values()])
                if workspace is None and draft is not None:
                    workspace = {"schema_version": 1, "active_id": "draft", "documents": [{"id": "draft", "graph": draft}],
                                 "closed_documents": [], "panel_widths": {"library": None, "inspector": None}}
                if workspace:
                    for document in workspace["documents"] + workspace["closed_documents"]:
                        document["graph"] = remap(rebase(document["graph"]))
                        if document.get("workflow_id") in ids:
                            document["workflow_id"] = ids[document["workflow_id"]]
                    # A complete, rebased copy also preserves overflow beyond the
                    # editor's 20 open / 20 closed page limits.
                    atomic_json(archive / "workspace.json", workspace)
                    current = library.load_workspace()
                    if current:
                        known = {json.dumps(d["graph"], sort_keys=True) for d in current["documents"] + current["closed_documents"]}
                        for document in workspace["documents"] + workspace["closed_documents"]:
                            if json.dumps(document["graph"], sort_keys=True) in known:
                                continue
                            document["id"] = f"migrated_{key}_" + sha256(document["id"].encode()).hexdigest()[:12]
                            target = current["documents"] if len(current["documents"]) < 20 else current["closed_documents"]
                            if len(target) < 20:
                                target.append(document)
                        workspace = current
                    library.save_workspace(Workspace.model_validate(workspace))
                library.changed()
                atomic_json(archive / "complete.json", {"version": 1, "source": str(old_data), "id_map": ids,
                    "completed_at": datetime.now(timezone.utc).isoformat(), "warnings": sorted(set(warnings)),
                    "history_preserved_at": str(old_data / "jobs")})
