"""Independent, transactional distribution of v3 operator/Reader libraries.

This is a transport envelope, not another operator protocol. The existing wheel
installer owns validation, dependency isolation, bytecode and generation locks.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import zipfile

from packaging.version import Version

from biopipe_sdk.protocol import PROTOCOL_VERSION


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_bundle(root, output, version):
    """Compile declarations statically; never import author operator modules."""
    from biopipe.registry import scan_sources, package_manifest, read_json
    from biopipe.source_library import snapshot_sources, provider_wheel
    root, output = Path(root), Path(output)
    version = str(Version(version))
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="library-build-", dir=output) as temporary:
        staging = Path(temporary)
        source = staging / "sources"
        snapshot_sources(root, source)
        records, errors = scan_sources(source)
        if errors:
            raise ValueError(json.dumps(errors, ensure_ascii=False))
        manifest = package_manifest(records, read_json(source / "biopipe/builtin_packages.json", {}))
        (source / "biopipe/builtin_packages.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        packages = []
        for package in manifest["packages"]:
            if not package["descriptors"]:
                continue
            wheel = provider_wheel(package, source, staging / "packages")
            packages.append({"name": package["name"], "version": package["version"],
                             "file": wheel.relative_to(staging).as_posix()})
        if not packages:
            raise ValueError("Library contains no operators or Readers")
        files = {p.relative_to(staging).as_posix(): sha256(p) for p in sorted(staging.rglob("*")) if p.is_file()}
        document = {"format": "biopipe.library", "version": version, "protocol_version": PROTOCOL_VERSION,
                    "minimum_application": "0.8.3", "packages": packages, "files": files}
        archive_path = staging / "library.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("library.json", json.dumps(document, indent=2))
            for relative in files:
                archive.write(staging / relative, relative)
        destination = output / f"BioPipe-Library-v{version}.biopipe-library.zip"
        os.replace(archive_path, destination)
    return {"bundle": str(destination.resolve()), "sha256": sha256(destination),
            "version": version, "packages": len(packages), "descriptors": sum(len(p['descriptors']) for p in manifest['packages'])}


def unpack_bundle(path, destination):
    from biopipe import __version__
    from biopipe.source_library import SOURCE_DIRS
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len({n.casefold() for n in names}) != len(names):
            raise ValueError("Duplicate library archive entries")
        for info in infos:
            name = info.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith('/') or '\\' in name or ':' in name
                    or any(p in {'.', '..'} or p.endswith(('.', ' ')) for p in parts)
                    or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError(f"Invalid library archive path: {name}")
        document = json.loads(archive.read("library.json"))
        if document.get("format") != "biopipe.library" or document.get("protocol_version") != PROTOCOL_VERSION:
            raise ValueError("A protocol v3 BioPipe library bundle is required; migrate old declarations first")
        Version(document['version'])
        if Version(__version__) < Version(document['minimum_application']):
            raise ValueError(f"Library requires BioPipe {document['minimum_application']} or newer")
        files, packages = document['files'], document['packages']
        if not isinstance(files, dict) or not isinstance(packages, list) or not packages:
            raise ValueError("Invalid library manifest")
        if set(names) != {'library.json', *files}:
            raise ValueError("Library archive contents differ from its manifest")
        wheel_paths = [p['file'] for p in packages]
        if len(set(wheel_paths)) != len(wheel_paths) or len({p['name'] for p in packages}) != len(packages):
            raise ValueError("Duplicate library packages")
        prefixes = [f"sources/{relative}/" for relative in SOURCE_DIRS.values()]
        for name, expected in files.items():
            wheel = name in wheel_paths and PurePosixPath(name).parent == PurePosixPath('packages') and name.endswith('.whl')
            if not wheel and name != 'sources/biopipe/builtin_packages.json' and not any(name.startswith(p) for p in prefixes):
                raise ValueError(f"Unexpected library file: {name}")
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output)
            if sha256(target) != expected:
                raise ValueError(f"Library checksum mismatch: {name}")
        from biopipe.dropins import wheel_name
        from biopipe.install_targets import wheel_entries
        from biopipe.source_library import provider_wheel
        manifest = json.loads((destination / 'sources/biopipe/builtin_packages.json').read_text(encoding='utf-8'))
        definitions = {p['name']: p for p in manifest['packages'] if p['descriptors']}
        if set(definitions) != {p['name'] for p in packages}:
            raise ValueError('Library sources and packages differ')
        for item in packages:
            wheel = destination / item['file']
            if wheel_name(wheel) != item['name'] or definitions[item['name']]['version'] != item['version']:
                raise ValueError('Library package identity mismatch')
            wheel_entries(wheel)  # Protocol and executable identity before invoking pip.
            rebuilt = provider_wheel(definitions[item['name']], destination / 'sources', destination / 'verified')
            if sha256(rebuilt) != sha256(wheel):
                raise ValueError(f"Library source does not match wheel: {item['name']}")
    return document


def install_bundle(manager, bundle):
    from biopipe.source_library import snapshot_sources
    manager.state()
    with manager.lock:
        current = manager.state()
        staging = manager.directory / 'staging'
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='library-', dir=staging) as temporary:
            temporary = Path(temporary)
            document = unpack_bundle(bundle, temporary / 'incoming')
            # Do not hide unrefreshed author edits behind a new source pointer.
            previous = current.get('source_library') or {}
            if manager.managed_sources and manager.source_root.exists():
                fingerprint = snapshot_sources(manager.source_root, temporary / 'existing')
                seed = manager.source_root / '.seed.json'
                expected = previous.get('sha256') or (json.loads(seed.read_text(encoding='utf-8'))['sha256'] if seed.is_file() else None)
                if fingerprint != expected:
                    raise ValueError('Local library sources have unrefreshed edits; refresh or export them before importing an update')
            incoming = temporary / 'incoming'
            installed = {p['name']: p['sha256'] for p in current['packages']}
            if ((current.get('library_release') or {}).get('sha256') == sha256(bundle)
                    and all(installed.get(p['name']) == document['files'][p['file']] for p in document['packages'])):
                return current
            identifier = uuid.uuid4().hex
            relative = f'library/sources/{identifier}'
            target = manager.directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            fingerprint = snapshot_sources(incoming / 'sources', temporary / 'snapshot')
            from biopipe_sdk.declarations import code_hash
            manifest = json.loads((incoming / 'sources/biopipe/builtin_packages.json').read_text(encoding='utf-8'))
            first = next(d for p in manifest['packages'] for d in p['descriptors'])
            receipt = {'root': relative, 'sha256': fingerprint,
                       'code_sha': code_hash(first['entry_point'], incoming / 'sources'),
                       'packages': [p['name'] for p in document['packages']]}
            state = manager._install_many([incoming / p['file'] for p in document['packages']], current,
                                          source_library=receipt, publish=False)
            # The immutable environment and editable source revision both exist
            # before the single atomic registry pointer becomes visible.
            os.replace(incoming / 'sources', target)
            state['library_release'] = {'version': document['version'], 'sha256': sha256(bundle)}
            from biopipe.plugins import atomic_json
            atomic_json(manager.directory / 'environments' / state['generation'] / 'lock.json', state)
            atomic_json(manager.registry, state)
            return state
