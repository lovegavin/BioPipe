"""Statically refresh the existing operator/Reader source library.

Source files are the authoring interface. Immutable provider wheels are an
internal implementation detail, sharing the existing package/runtime protocol.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from biopipe.plugins import ROOT
from biopipe_sdk.protocol import PROTOCOL_VERSION

SOURCE_DIRS = {"operator": "src/task/step/steps", "reader": "src/reader/readers"}


def directories(root=ROOT):
    if root is None:
        return {}
    return {kind: root / relative for kind, relative in SOURCE_DIRS.items()}


def provider_wheel(package, root, output):
    from biopipe.dropins import write_wheel
    from packaging.version import Version
    name, version = package["name"], str(Version(package["version"]))
    module = "biopipe_library_" + name.replace("-", "_").replace(".", "_")
    prefixes = {SOURCE_DIRS["operator"].replace("/", "."): module + ".steps",
                SOURCE_DIRS["reader"].replace("/", "."): module + ".readers"}
    def rewrite(value):
        for before, after in prefixes.items():
            value = value.replace(before, after)
        return value
    files = {}
    # Copy the small module trees, preserving helper/cross-operator imports in a
    # private namespace. No new source can overwrite the engine's src package.
    for kind, relative in SOURCE_DIRS.items():
        folder = "steps" if kind == "operator" else "readers"
        for source in sorted((root / relative).rglob("*")):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                path = source.relative_to(root / relative).as_posix()
                files[f"{module}/{folder}/{path}"] = (rewrite(source.read_text(encoding="utf-8")).encode("utf-8")
                    if source.suffix == ".py" else source.read_bytes())
    definitions = deepcopy(package["descriptors"])
    files[f"{module}/__init__.py"] = b'"""Immutable provider code; parameters live in per-operator JSON."""\n'
    # Hash the exact rewritten bytes that the wheel will install.
    digest = hashlib.sha256()
    for relative, data in sorted(files.items()):
        if relative.endswith('.py'):
            digest.update(relative.encode() + b'\0')
            digest.update(data.decode('utf-8').replace('\r\n', '\n').encode('utf-8'))
    from biopipe_sdk.declarations import declaration_hash
    groups = {'operator': [], 'reader': []}
    for descriptor in definitions:
        descriptor['entry_point'] = rewrite(descriptor['entry_point'])
        descriptor['code_sha'] = digest.hexdigest()
        descriptor['declaration_sha'] = declaration_hash(descriptor)
        groups[descriptor['kind']].append(f"{descriptor['id']} = {descriptor['entry_point']}")
    document = {"protocol_version": PROTOCOL_VERSION, "name": name, "version": version, "descriptors": definitions}
    info = f"{name.replace('-', '_').replace('.', '_')}-{version}.dist-info"
    entries = []
    for kind, group in (("operator", "operators"), ("reader", "readers")):
        if groups[kind]:
            entries.extend([f"[biopipe.{group}]", *groups[kind], ""])
    files[f"{info}/entry_points.txt"] = "\n".join(entries).encode()
    files[f"{info}/biopipe.json"] = json.dumps(document).encode()
    return write_wheel(files, name, version, [], output)


def prepare(manager, current, temporary):
    """Capture exact bytes before scanning; no source tree or shipped index edits."""
    from biopipe.dropins import snapshot
    root = manager.source_root
    if root is None:
        return {"wheels": [], "updated": [], "unchanged": [], "receipt": current.get("source_library")}
    staged = temporary / "source"
    digest = hashlib.sha256()
    for relative in [*SOURCE_DIRS.values(), "biopipe/builtin_packages.json"]:
        source = root / relative
        target = staged / relative if source.is_dir() else (staged / relative).parent
        digest.update(relative.encode() + snapshot(source, target).encode())
    fingerprint = digest.hexdigest()
    previous = current.get("source_library", {})
    if previous.get("sha256") == fingerprint:
        return {"wheels": [], "updated": [], "unchanged": ["operator / Reader source directories"], "receipt": previous}
    from biopipe.registry import scan_sources, package_manifest, read_json
    records, errors = scan_sources(staged)
    if errors:
        raise ValueError('; '.join(f"{e['source']}: {e['error']}" for e in errors))
    manifest = package_manifest(records, read_json(staged / 'biopipe/builtin_packages.json', {'packages': []}))
    installed = {p["name"]: p for p in current["packages"]}
    source_managed = set(previous.get("packages", []))
    seen = set(current.get("bundled_seen", []))
    packages = [p for p in manifest["packages"] if p["descriptors"] and
                (installed.get(p["name"], {}).get("origin") == "bundled" or
                 (p["name"] in source_managed and p["name"] in installed) or
                 p["name"] not in installed and p["name"] not in seen)]
    from biopipe_sdk.declarations import declaration_hash, code_hash
    from biopipe.metadata_updates import replace_declarations
    code_sha = code_hash(records[0][0]['entry_point'], staged) if records else hashlib.sha256(b'').hexdigest()
    old_code = previous.get('code_sha') or next((d['code_sha'] for d in current['descriptors'] if d.get('origin') == 'bundled'), None)
    candidate = []
    old = {d['id']: d for d in current['descriptors']}
    for package in packages:
        for descriptor in package['descriptors']:
            if descriptor['id'] not in old:
                continue
            d = deepcopy(descriptor)
            d['entry_point'] = old[d['id']]['entry_point']
            d['code_sha'] = old[d['id']]['code_sha']
            # Installation may add a host SDK requirement from wheel metadata.
            d['dependencies'] = sorted(set(d.get('dependencies', [])) | {v for v in old[d['id']].get('dependencies', []) if v.lower().startswith('biopipe-studio')})
            d['declaration_sha'] = declaration_hash(d)
            candidate.append(d)
    receipt = {'sha256': fingerprint, 'code_sha': code_sha, 'packages': [p['name'] for p in packages]}
    same_ids = {d['id'] for d in candidate} == {d['id'] for p in packages for d in p['descriptors']}
    if code_sha == old_code and same_ids:
        # Validate the entire transaction before publishing any change.
        state = replace_declarations(current, candidate)
        return {'wheels': [], 'updated': [p['name'] for p in packages], 'unchanged': [],
                'receipt': receipt, 'state': state}
    wheels = [provider_wheel(p, staged, temporary / "wheels") for p in packages]
    return {"wheels": wheels, "updated": [p["name"] for p in packages], "unchanged": [],
            "receipt": receipt}
