"""One-time v1/v2-to-v3 conversion at the desktop upgrade boundary or CLI.

Preflight is read-only. --apply backs up every changed file before publishing;
failed publication restores original bytes. Completed jobs and pinned snapshots
are historical evidence and are deliberately outside profile migration.
"""
from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
import ast
import hashlib
import json
import math
from pathlib import Path
import pprint
import uuid

import yaml

from biopipe_sdk.protocol import PROTOCOL_VERSION, validate_parameters


def _json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def descriptors(value):
    """Flatten old manifests without importing their Python implementations."""
    if isinstance(value, list):
        return [d for item in value for d in descriptors(item)]
    if not isinstance(value, dict):
        return []
    if "id" in value and "parameters_schema" in value:
        return [value]
    return list(value.get("descriptors", [])) + [d for p in value.get("packages", []) for d in p.get("descriptors", [])]


def _parameters(schema, params, output_parameter=None, *, draft=False):
    value = deepcopy(params)
    for key, rule in schema.get("properties", {}).items():
        item = value.get(key)
        kind = rule.get("type")
        if isinstance(item, str) and kind in ("number", "integer"):
            try:
                number = float(item)
            except ValueError:
                continue
            if math.isfinite(number) and (kind != "integer" or number.is_integer()):
                value[key] = int(number) if kind == "integer" else number
    output = value.pop(output_parameter, None) if output_parameter else None
    if draft:
        # An editable canvas need not be runnable yet. Keep missing fields
        # missing; validate supplied values and freeze real defaults as usual.
        schema = deepcopy(schema)
        schema.pop('required', None)
    value = validate_parameters(schema, value)
    if output is not None:
        value[output_parameter] = output
    return value


def convert_documents(value, catalog, *, implementations=None, changes=None):
    """Convert graphs (including nested routes and undo snapshots) recursively."""
    changes = [] if changes is None else changes
    if isinstance(value, list):
        return [convert_documents(item, catalog, implementations=implementations, changes=changes) for item in value]
    if not isinstance(value, dict):
        return deepcopy(value)
    result = {key: convert_documents(item, catalog, implementations=implementations, changes=changes)
              for key, item in value.items()}
    if "documents" in result and "active_id" in result:
        from src.web.models import Workspace
        result = Workspace.model_validate(result).model_dump(mode="json")
    if not (isinstance(result.get("nodes"), list) and isinstance(result.get("edges"), list)):
        return result
    # Agent presence and selection events also have nodes/edges arrays, but
    # contain selected IDs rather than a graph. Empty selections need this
    # discriminator too; they must not acquire a graph schema during migration.
    if not ("schema_version" in result or "name" in result or
            any(isinstance(node, dict) and "kind" in node for node in result["nodes"])):
        return result
    if result.get("schema_version", 1) not in (1, 2):
        raise ValueError("Cannot migrate an unknown graph schema version")
    result["schema_version"] = 2
    specs = {d["id"]: d for d in catalog}
    for node in result["nodes"]:
        if node.get("kind") != "operator":
            continue
        pin = result.get('plugin_lock', {}).get(node.get('operator'), {})
        if all(isinstance(pin.get(k), str) and len(pin[k]) == 64 for k in ('code_sha', 'declaration_sha')):
            # Its defaults belong to a frozen v3 snapshot, not today's catalog.
            continue
        spec = specs.get(node.get("operator"))
        if spec is None:
            raise ValueError(f"Missing v3 operator {node.get('operator')}; rebuild/install its provider before migration")
        before = node.get("params", {})
        node["params"] = _parameters(spec["parameters_schema"], before, spec.get("output_parameter"), draft=True)
        if node["params"] != before:
            changes.append({"node": node["id"], "reason": "Execution defaults and numeric values made explicit"})
    for key, before in result.get("plugin_lock", {}).items():
        current = (implementations or {}).get(key)
        is_v3 = all(isinstance(before.get(k), str) and len(before[k]) == 64 for k in ('code_sha', 'declaration_sha'))
        if not is_v3 and current and before.get("package") == current.get("package") and before != current:
            result["plugin_lock"][key] = deepcopy(current)
            changes.append({"operator": key, "before": before, "after": current, "reason": "Explicit protocol v3 migration"})
    from src.web.models import Graph
    return Graph.model_validate(result).model_dump(mode="json")


def convert_task(value, catalog):
    result = deepcopy(value)
    specs = {d["id"]: d for d in catalog if d["kind"] == "operator"}
    if not isinstance(result.get("sources"), dict) or not isinstance(result.get("steps"), list):
        raise ValueError("Task requires sources and steps")
    for step in result["steps"]:
        spec = specs.get(step.get("name"))
        if spec is None:
            raise ValueError(f"Missing v3 operator: {step.get('name')}")
        step["params"] = _parameters(spec["parameters_schema"], step.get("params", {}), spec.get("output_parameter"))
    return result


def convert_source_parts(text, manifest, *, source_name=None):
    """Split known v1/v2 metadata into literal protocol + per-class parameter JSON.

    The supplied old manifest is the evidence; migration never executes code.
    """
    from biopipe_sdk.declarations import DECLARATION_ATTRIBUTES
    from biopipe_sdk.protocol import Descriptor
    definitions = descriptors(manifest)
    lines = text.splitlines(keepends=True)
    edits, parameters = [], {}
    for cls in [n for n in ast.parse(text).body if isinstance(n, ast.ClassDef)]:
        candidates = [d for d in definitions if d.get('entry_point', '').split(':')[-1] == cls.name]
        if not candidates:
            continue
        if len(candidates) != 1:
            raise ValueError(f'Ambiguous descriptor for {cls.name}; supply one provider manifest')
        descriptor = deepcopy(candidates[0])
        filename = (source_name + '.' if source_name else '') + cls.name + '.parameters.json'
        schema = descriptor['parameters_schema']
        for field in descriptor.get('parameters', []):
            prop = schema.get('properties', {}).get(field['key'])
            if prop is not None and 'default' in field and field['default'] != prop.get('default'):
                prop['x-ui-default'] = deepcopy(field['default'])
        parameters[filename] = schema
        definition = {k: v for k, v in descriptor.items() if k in Descriptor.model_fields
                      and k not in {'parameters_schema', 'entry_point', 'code_sha', 'declaration_sha', 'icon_image'}}
        definition['protocol_version'] = PROTOCOL_VERSION
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            names = {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
            if names and names <= DECLARATION_ATTRIBUTES | {'definition', 'parameters_file'}:
                edits.append((node.lineno-1, node.end_lineno, ''))
        offset = cls.body[0].end_lineno if isinstance(cls.body[0], ast.Expr) and isinstance(cls.body[0].value, ast.Constant) and isinstance(cls.body[0].value.value, str) else cls.lineno
        block = '    parameters_file = ' + repr(filename) + '\n    definition = ' + pprint.pformat(definition, width=100, sort_dicts=False).replace('\n', '\n    ') + '\n'
        edits.append((offset, offset, block))
    if not parameters:
        raise ValueError('No implementation classes match the supplied old manifest')
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]
    result = ''.join(lines)
    ast.parse(result)
    return result, parameters


def convert_source(text, manifest):
    return convert_source_parts(text, manifest)[0]


def _current():
    from biopipe.packages import bundled_state
    return bundled_state()


def _profile_plan(directory, current):
    from biopipe.client import instances
    if instances(directory):
        raise ValueError("Close every Studio instance using this profile before migration")
    registry = directory / "plugins/registry.json"
    registry_bytes = registry.read_bytes() if registry.exists() else None
    old = json.loads(registry_bytes.decode("utf-8-sig")) if registry_bytes is not None else None
    active = deepcopy(current)
    if old:
        if old.get("package_protocol_version") not in (None, 1, 2, PROTOCOL_VERSION):
            raise ValueError("Cannot migrate an unknown library protocol version")
        external = [p["name"] for p in old.get("packages", []) if p.get("origin") != "bundled"]
        if external and old.get("package_protocol_version") != PROTOCOL_VERSION:
            raise ValueError("Rebuild old external providers for v3 before profile conversion: " + ", ".join(external) + ". Keep the old profile for v0.4.1; install rebuilt providers into a separate v3 profile and migrate exported workflows there.")
        if old.get("package_protocol_version") == PROTOCOL_VERSION:
            active = deepcopy(old)
        else:
            old_packages = {p["name"]: p for p in old.get("packages", [])}
            seen = set(old.get("bundled_seen", old_packages))
            if not old.get("package_protocol_version"):
                seen = set()
            active["packages"] = [{**p, "enabled": old_packages.get(p["name"], {}).get("enabled", True)}
                                  for p in current["packages"] if p["name"] in old_packages or p["name"] not in seen]
            allowed = {p["name"] for p in active["packages"]}
            active["descriptors"] = [d for d in current["descriptors"] if d["distribution"] in allowed]
            active.update(protocol_version=PROTOCOL_VERSION, package_protocol_version=PROTOCOL_VERSION,
                          bundled_seen=sorted(seen | {p["name"] for p in current["packages"]}), generation=uuid.uuid4().hex)
    catalog = active["descriptors"]
    implementations = {d["id"]: d["implementation"] for d in catalog}
    changes, updates, originals = [], {}, {}
    paths = [*sorted((directory / "workflows").glob("*.json")), *sorted((directory / "agent/sessions").glob("*.json"))]
    draft = directory / "draft.json"
    if draft.exists():
        paths.append(draft)
    for path in paths:
        content = path.read_bytes()
        before = json.loads(content.decode("utf-8-sig"))
        after = convert_documents(before, catalog, implementations=implementations, changes=changes)
        if before != after:
            updates[path] = _json(after)
            originals[path] = content
    if old and old.get("package_protocol_version") != PROTOCOL_VERSION:
        updates[registry] = _json(active)
        originals[registry] = registry_bytes
        updates[directory / "plugins/snapshots" / (active["generation"] + ".json")] = _json(active)
    # Convert the abandoned single-page storage once. Runtime reads only workspace.
    workspace = directory / "workflows/workspace.json"
    if draft.exists() and not workspace.exists():
        graph = convert_documents(_read(draft), catalog, implementations=implementations, changes=changes)
        updates[workspace] = _json({"schema_version": 1, "active_id": "migrated", "documents": [{"id": "migrated", "graph": graph}], "closed_documents": []})
    return updates, changes, {p: originals.get(p) for p in updates}


def _publish(updates, backup_root, *, expected=None):
    """Back up first; verify inputs did not change; roll back a failed batch."""
    from src.web.storage import atomic_json
    originals = {p: p.read_bytes() if p.exists() else None for p in updates}
    if expected is not None:
        for path, content in originals.items():
            if content != expected[path]:
                raise ValueError(f"File changed after migration preflight: {path}")
    backup = Path(backup_root) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, exist_ok=False)
    records = []
    for index, (path, content) in enumerate(originals.items()):
        name = f"{index:04d}.original"
        if content is not None:
            (backup / name).write_bytes(content)
        records.append({"path": str(path), "backup": name if content is not None else None,
                        "before_sha256": hashlib.sha256(content).hexdigest() if content is not None else None,
                        "after_sha256": hashlib.sha256(updates[path]).hexdigest()})
    atomic_json(backup / "manifest.json", {"protocol_version": PROTOCOL_VERSION, "files": records, "status": "prepared"})
    written = []
    try:
        for path, content in updates.items():
            actual = path.read_bytes() if path.exists() else None
            if actual != originals[path]:
                raise ValueError(f"File changed during migration: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".migration-" + uuid.uuid4().hex)
            try:
                temporary.write_bytes(content)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
            written.append(path)
    except BaseException:
        for path in reversed(written):
            if originals[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(originals[path])
        atomic_json(backup / "manifest.json", {"protocol_version": PROTOCOL_VERSION, "files": records, "status": "rolled_back"})
        raise
    atomic_json(backup / "manifest.json", {"protocol_version": PROTOCOL_VERSION, "files": records, "status": "complete"})
    return str(backup)


def migrate(*, path=None, profile_dir=None, workspace=None, data_dir=None, manifest=None, apply=False):
    current = _current()
    if path is not None and (profile_dir is not None or workspace is not None):
        from biopipe.client import data_directory
        from biopipe.plugins import require_current_state
        registry = data_directory(profile_dir, workspace, data_dir) / "plugins/registry.json"
        if registry.exists():
            current = _read(registry)
            require_current_state(current)
    changes = []
    if path is not None:
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError("Migration path must be an existing .json, .yaml, .yml, or .py file")
        original = path.read_bytes()
        source = original.decode("utf-8-sig")
        if path.suffix == ".py":
            if manifest is None:
                raise ValueError("Source migration requires --manifest pointing to its old descriptor/registry JSON")
            code, parameter_files = convert_source_parts(source, _read(manifest), source_name=path.stem)
            result = code.encode("utf-8")
        elif path.suffix.lower() in (".yaml", ".yml"):
            value = convert_task(yaml.safe_load(source), current["descriptors"])
            result = yaml.safe_dump(value, sort_keys=False, allow_unicode=True).encode("utf-8")
        elif path.suffix.lower() == ".json":
            value = convert_documents(json.loads(source), current["descriptors"],
                                      implementations={d["id"]: d["implementation"] for d in current["descriptors"]}, changes=changes)
            result = _json(value)
        else:
            raise ValueError("Unsupported migration file type")
        updates = {path: result} if original != result else {}
        if path.suffix == '.py':
            for name, schema in parameter_files.items():
                target = path.parent / name
                content = _json(schema)
                if target.exists() and target.read_bytes() != content:
                    raise ValueError(f'Parameter file already exists with different content: {target}; review it before migration')
                if not target.is_file() or target.read_bytes() != content:
                    updates[target] = content
        backup_root = path.parent / ".biopipe-migration-backups"
    else:
        from biopipe.client import data_directory
        from src.web.storage import FileLock
        directory = data_directory(profile_dir, workspace, data_dir)
        if not directory.is_dir():
            raise ValueError(f"No existing Studio data directory: {directory}")
        # A dedicated lock protects migration invocations; Studio must be closed.
        with FileLock(directory / ".migration.lock") if apply else nullcontext():
            updates, changes, originals = _profile_plan(directory, current)
            backup = _publish(updates, directory / "migrations/v3", expected=originals) if apply and updates else None
        return {"protocol_version": PROTOCOL_VERSION, "apply": apply, "changed": [str(p) for p in updates], "backup": backup, "details": changes}
    backup = _publish(updates, backup_root, expected={p: original if p == path else p.read_bytes() if p.exists() else None for p in updates}) if apply and updates else None
    return {"protocol_version": PROTOCOL_VERSION, "apply": apply, "changed": [str(p) for p in updates], "backup": backup, "details": changes}
