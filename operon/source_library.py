"""Statically refresh the existing operator/Reader source library.

Source files are the authoring interface. Immutable provider wheels are an
internal implementation detail, sharing the existing package/runtime protocol.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import os

from operon.plugins import ROOT
from operon_sdk.protocol import PROTOCOL_VERSION

SOURCE_DIRS = {"operator": "src/task/step/steps", "reader": "src/reader/readers"}


def directories(root=ROOT):
    if root is None:
        return {}
    from .library_location import source_root
    root = source_root(root)
    return {kind: root / relative for kind, relative in SOURCE_DIRS.items()}


def snapshot_sources(root, staged=None):
    from operon.dropins import snapshot
    from .library_location import source_root
    root = source_root(root)
    digest = hashlib.sha256()
    for relative in [*SOURCE_DIRS.values(), "operon/builtin_packages.json"]:
        source = root / relative
        target = (staged / relative if source.is_dir() else (staged / relative).parent) if staged is not None else None
        digest.update(relative.encode() + snapshot(source, target).encode())
    return digest.hexdigest()


def seed_sources(seed, target):
    """Never overwrite an existing authoring tree during an application update."""
    if target.exists():
        if not (target / "operon/builtin_packages.json").is_file():
            raise ValueError(f"Incomplete library source directory: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="seed-", dir=target.parent) as temporary:
        staged = Path(temporary) / "sources"
        fingerprint = snapshot_sources(seed, staged)
        (staged / '.seed.json').write_text(json.dumps({'sha256': fingerprint}), encoding='utf-8')
        os.replace(staged, target)


def provider_wheel(package, root, output):
    from .library_location import source_root
    root = source_root(root)
    from operon.dropins import write_wheel
    from packaging.version import Version
    name, version = package["name"], str(Version(package["version"]))
    module = "operon_library_" + name.replace("-", "_").replace(".", "_")
    prefixes = {SOURCE_DIRS["operator"].replace("/", "."): module + ".steps",
                SOURCE_DIRS["reader"].replace("/", "."): module + ".readers"}
    def rewrite(value):
        for before, after in prefixes.items():
            value = value.replace(before, after)
        return value
    files = {}
    document_paths = set()
    for descriptor in package['descriptors']:
        if descriptor.get('documentation'):
            source = Path(root) / (descriptor['entry_point'].split(':')[0].replace('.', '/') + '.py')
            if not source.is_file():
                source = source.with_suffix('') / '__init__.py'
            document_paths.add((source.parent / descriptor['documentation']['path']).resolve())
    # Copy the small module trees, preserving helper/cross-operator imports in a
    # private namespace. No new source can overwrite the engine's src package.
    for kind, relative in SOURCE_DIRS.items():
        folder = "steps" if kind == "operator" else "readers"
        for source in sorted((root / relative).rglob("*")):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix != '.pyc':
                # Providers share helper Python but ship only their own declared
                # documentation. A different provider's docs cannot alter this
                # provider's executable digest.
                if source.suffix.lower() == '.md' and source.resolve() not in document_paths:
                    continue
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
    from operon_sdk.declarations import declaration_hash
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
            entries.extend([f"[operon.{group}]", *groups[kind], ""])
    files[f"{info}/entry_points.txt"] = "\n".join(entries).encode()
    files[f"{info}/operon.json"] = json.dumps(document).encode()
    return write_wheel(files, name, version, [], output)


def prepare(manager, current, temporary):
    """Capture exact bytes before scanning; no source tree or shipped index edits."""
    root = manager.source_root
    if root is None:
        return {"wheels": [], "updated": [], "unchanged": [], "receipt": current.get("source_library")}
    from operon.bytecode import filesystem_path
    previous = current.get("source_library") or {}
    if manager.managed_sources and manager.manifest_only and not previous:
        # An explicit refresh is not an installation. A pristine editable copy
        # can keep the already indexed factory providers and their exact pins.
        # Compare bytes (including JSON/docs), not a seed marker or file times:
        # edits made before the first refresh must still enter the transaction.
        if snapshot_sources(root) == snapshot_sources(ROOT):
            return {"wheels": [], "updated": [],
                    "unchanged": ["factory operator / Reader source directories"],
                    "receipt": current.get("source_library")}
    needs_detach = manager.managed_sources and any(p.get('origin') == 'bundled' for p in current['packages'])
    if previous.get("sha256") and not needs_detach and previous['sha256'] == snapshot_sources(root):
        receipt = deepcopy(previous)
        if manager.managed_sources:
            receipt['root'] = root.relative_to(manager.directory.resolve()).as_posix()
        return {"wheels": [], "updated": [], "unchanged": ["operator / Reader source directories"], "receipt": receipt}
    # Changed sources still get an immutable byte-for-byte snapshot. Hashing a
    # no-op refresh must not copy thousands of files into a staging directory.
    staged = Path(filesystem_path(temporary / "source", resolve=False))
    fingerprint = snapshot_sources(root, staged)
    from operon.registry import scan_sources, package_manifest, read_json
    records, errors = scan_sources(staged)
    if errors:
        raise ValueError('; '.join(f"{e['source']}: {e['error']}" for e in errors))
    manifest = package_manifest(records, read_json(staged / 'operon/builtin_packages.json', {'packages': []}))
    from operon.operator_docs import cache_sources
    cache_sources(manager, [record[0] for record in records], staged)
    installed = {p["name"]: p for p in current["packages"]}
    source_managed = set(previous.get("packages", []))
    seen = set(current.get("bundled_seen", []))
    packages = [p for p in manifest["packages"] if p["descriptors"] and
                (installed.get(p["name"], {}).get("origin") == "bundled" or
                 (p["name"] in source_managed and p["name"] in installed) or
                 p["name"] not in installed and p["name"] not in seen)]
    from operon_sdk.declarations import declaration_hash, code_hash
    from operon.metadata_updates import replace_declarations
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
            d['dependencies'] = sorted(set(d.get('dependencies', [])) | {v for v in old[d['id']].get('dependencies', []) if v.lower().startswith('operon-studio')})
            d['declaration_sha'] = declaration_hash(d)
            candidate.append(d)
    receipt = {'sha256': fingerprint, 'code_sha': code_sha, 'packages': [p['name'] for p in packages]}
    if manager.managed_sources:
        receipt['root'] = root.relative_to(manager.directory.resolve()).as_posix()
    same_ids = {d['id'] for d in candidate} == {d['id'] for p in packages for d in p['descriptors']}
    detach = manager.managed_sources and any(installed.get(p['name'], {}).get('origin') == 'bundled' for p in packages)
    if code_sha == old_code and same_ids and not detach:
        # Validate the entire transaction before publishing any change.
        state = replace_declarations(current, candidate)
        return {'wheels': [], 'updated': [p['name'] for p in packages], 'unchanged': [],
                'receipt': receipt, 'state': state}
    wheels = [provider_wheel(p, staged, temporary / "wheels") for p in packages]
    return {"wheels": wheels, "updated": [p["name"] for p in packages], "unchanged": [],
            "receipt": receipt}
