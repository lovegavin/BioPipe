"""Explicit drop-folder snapshots, converted to ordinary immutable plugin wheels."""
from __future__ import annotations

import ast
import base64
from copy import deepcopy
import csv
import hashlib
import io
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from biopipe_sdk.icons import icon_path, is_image_icon

from biopipe.plugins import run_process

IGNORED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache",
           ".ruff_cache", "build", "dist", "node_modules"}


def source_files(path):
    """Never follow symlinks/junctions out of a package's source tree."""
    if path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
        raise ValueError(f"Linked files/directories are not supported: {path.name}")
    if path.is_file():
        yield path
    elif path.is_dir():
        for child in sorted(path.iterdir()):
            if child.name in IGNORED or child.name.endswith((".egg-info", ".pyc", ".pyo")):
                continue
            yield from source_files(child)


def snapshot(source, target):
    """Hash the bytes actually staged, so an editor cannot change a pending install."""
    digest = hashlib.sha256()
    for path in source_files(source):
        relative = path.relative_to(source) if source.is_dir() else Path(source.name)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_hash = hashlib.sha256()
        with path.open("rb") as reader, destination.open("wb") as writer:
            while block := reader.read(1024 * 1024):
                writer.write(block)
                file_hash.update(block)
        digest.update(relative.as_posix().encode("utf-8") + b"\0" + file_hash.digest())
    return digest.hexdigest()


def module_assets(source):
    """Resolve each operator's parameter JSON and optional icon without imports."""
    from biopipe_sdk.declarations import source_declarations
    records = source_declarations(source, source.stem)
    assets = set()
    tree = ast.parse(source.read_text(encoding='utf-8'))
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if any(isinstance(t, ast.Name) and t.id == 'parameters_file' for t in targets):
                assets.add(ast.literal_eval(node.value))
        if any(d['entry_point'].endswith(':' + cls.name) for d in records) and not any(
                isinstance(n, (ast.Assign, ast.AnnAssign)) and any(isinstance(t, ast.Name) and t.id == 'parameters_file'
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target])) for n in cls.body):
            assets.add('parameters.json' if source.stem == '__init__' else source.stem + '.parameters.json')
    for d in records:
        if is_image_icon(d.get('icon')):
            assets.add(d['icon'])
    return sorted(assets)


def snapshot_module(source, target):
    digest = hashlib.sha256(snapshot(source, target).encode())
    for relative in module_assets(source):
        path = (source.parent / relative).resolve()
        if not path.is_relative_to(source.parent.resolve()):
            raise ValueError('Operator assets must remain inside the source directory')
        destination = target / relative.replace("\\", "/")
        digest.update(relative.encode() + snapshot(path, destination.parent).encode())
    return digest.hexdigest()


def single_file_wheel(source, output):
    """Wrap one code module and its parameter JSON files, without build tools."""
    import json
    from biopipe_sdk.declarations import source_declarations, compile_declaration, declaration_hash
    from biopipe_sdk.drift import check_source
    settings = {}
    for node in ast.parse(source.read_bytes()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BIOPIPE_PLUGIN' for t in node.targets):
            settings = ast.literal_eval(node.value)
    suffix = hashlib.sha256(source.name.encode()).hexdigest()[:12]
    slug = re.sub(r'[^a-z0-9]+', '-', source.stem.lower()).strip('-') or 'operator'
    name = canonicalize_name(settings.get('name', f'biopipe-dropin-{slug}-{suffix}'))
    version = str(Version(settings.get('version', '0.1.0')))
    from biopipe_sdk.dependencies import requirements
    dependencies = requirements(settings.get('dependencies', []))
    module = 'biopipe_dropin_' + hashlib.sha256(name.encode()).hexdigest()[:16]
    info = f"{name.replace('-', '_').replace('.', '_')}-{version}.dist-info"
    content = source.read_text(encoding='utf-8').encode('utf-8')
    files = {f'{module}/__init__.py': content}
    for relative in module_assets(source):
        files[f'{module}/{relative.replace(chr(92), "/")}'] = (source.parent / relative).read_bytes()
    code_sha = hashlib.sha256(f'{module}/__init__.py'.encode() + b'\0' + content).hexdigest()
    records = []
    for declaration in source_declarations(source, source.stem):
        d = compile_declaration(declaration, source.parent)
        errors, warnings = check_source(content.decode('utf-8'), d)
        if errors:
            raise ValueError('; '.join(errors))
        d['entry_point'] = module + ':' + d['entry_point'].split(':')[1]
        d['code_sha'] = code_sha
        d['declaration_sha'] = declaration_hash(d)
        records.append(d)
    if not records:
        raise ValueError('No v3 operator or Reader definitions')
    entries = []
    for kind, group in [('operator', 'operators'), ('reader', 'readers')]:
        entries += [f'[biopipe.{group}]', *[f"{d['id']} = {d['entry_point']}" for d in records if d['kind'] == kind], '']
    files[f'{info}/entry_points.txt'] = '\n'.join(entries).encode()
    files[f'{info}/biopipe.json'] = json.dumps({'protocol_version': 3, 'name': name, 'version': version, 'descriptors': records}).encode()
    return write_wheel(files, name, version, dependencies, output)


def write_wheel(files, name, version, dependencies, output):
    """A deterministic pure-Python wheel, including standard RECORD hashes."""
    distribution = name.replace("-", "_").replace(".", "_")
    info = f"{distribution}-{version}.dist-info"
    metadata = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}",
                "Requires-Python: >=3.11", *[f"Requires-Dist: {d}" for d in dependencies], "", ""]
    files[f"{info}/METADATA"] = "\n".join(metadata).encode()
    files[f"{info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: BioPipe library\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    rows = []
    for path, data in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append([path, "sha256=" + digest, str(len(data))])
    record = io.StringIO(newline="")
    csv.writer(record, lineterminator="\n").writerows([*rows, [f"{info}/RECORD", "", ""]])
    files[f"{info}/RECORD"] = record.getvalue().encode()
    output.mkdir(parents=True, exist_ok=True)
    wheel = output / f"{distribution}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path, data in files.items():
            # Fixed timestamps make a re-wrapped source byte-identical on other machines.
            entry = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    return wheel


def wheel_name(path):
    from email.parser import BytesParser
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("Invalid wheel metadata")
        return canonicalize_name(BytesParser().parsebytes(archive.read(names[0]))["Name"])


def refresh(manager, current):
    """Caller holds the installation lock. Missing inputs do not uninstall packages."""
    inbox = manager.inbox
    receipts = deepcopy(current.get("dropin_receipts", {}))
    sources = [p for p in sorted(inbox.iterdir()) if not p.name.startswith((".", "_")) and
               (p.suffix.lower() in {".py", ".whl"} or p.is_dir()) and
               not (p.is_dir() and p.name in {"icons", "assets"} and not (p / "pyproject.toml").exists())]
    staging = manager.directory / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    changed, skipped, wheels, owners, extra_packages = [], [], [], {}, set()
    metadata_changed = False
    with tempfile.TemporaryDirectory(prefix="scan-", dir=staging) as temporary:
        temporary = Path(temporary)
        from biopipe.source_library import prepare
        library = prepare(manager, current, temporary / "library")
        current = library.get("state", current)
        wheels.extend(library["wheels"])
        changed.extend(library["updated"])
        skipped.extend(library["unchanged"])
        owners.update({wheel_name(w): "operator / Reader source directories" for w in library["wheels"]})
        for index, source in enumerate(sources):
            try:
                target = temporary / str(index) / "source"
                digest = snapshot_module(source, target) if source.suffix.lower() == ".py" else snapshot(source, target)
                previous = receipts.get(source.name, {})
                if previous.get("sha256") == digest:
                    skipped.append(source.name)
                    if previous.get("package"):
                        if previous["package"] in owners:
                            raise ValueError(f"Duplicate package {previous['package']} in {owners[previous['package']]}")
                        owners[previous["package"]] = source.name
                    continue
                output = temporary / str(index) / "wheels"
                if source.is_dir():
                    if not (target / "pyproject.toml").is_file():
                        raise ValueError("A plugin folder must contain pyproject.toml with BioPipe entry points")
                    from biopipe.developer import build, check_source
                    manifest = check_source(target)
                    package = manifest['name']
                    # Parameter-only edits do not even invoke the wheel builder.
                    candidates = [{**d, 'dependencies': sorted(set(d.get('dependencies', []) + manifest.get('dependencies', [])))} for d in manifest['descriptors']]
                    updated = metadata_candidate(current, package, candidates, version=manifest['version'])
                    if updated is not None:
                        if package in owners:
                            raise ValueError(f'Duplicate package {package}')
                        owners[package] = source.name
                        current, metadata_changed = updated, True
                        receipts[source.name] = {'sha256': digest, 'package': package}
                        changed.append(source.name)
                        continue
                    wheel = Path(build(target)['wheels'][0])
                elif source.suffix.lower() == ".py":
                    wheel = single_file_wheel(target / source.name, output)
                else:
                    wheel = target / source.name
                package = wheel_name(wheel)
                if package in owners:
                    raise ValueError(f"Duplicate package {package} in {owners[package]}; keep only one input per package")
                owners[package] = source.name
                extra_packages.add(package)
                receipts[source.name] = {"sha256": digest, "package": package}
                from biopipe.install_targets import wheel_entries
                candidates = [{**e['expected'], 'dependencies': e['dependencies']} for e in wheel_entries(wheel)]
                with zipfile.ZipFile(wheel) as archive:
                    from email.parser import BytesParser
                    wheel_version = BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))['Version']
                updated = metadata_candidate(current, package, candidates, version=wheel_version)
                if updated is not None:
                    current, metadata_changed = updated, True
                else:
                    wheels.append(wheel)
                changed.append(source.name)
            except Exception as exc:
                raise ValueError(f"{source.name}: {exc}") from exc
        if wheels:
            try:
                receipt = deepcopy(library["receipt"])
                if receipt:
                    receipt["packages"] = [name for name in receipt["packages"] if name not in extra_packages]
                state = manager._install_many(wheels, current, receipts=receipts, source_library=receipt)
            except Exception as exc:
                raise ValueError(f"Refresh failed ({', '.join(changed)}); previous registry retained. {exc}") from exc
        else:
            state = current
            if metadata_changed or library.get("receipt") != current.get("source_library") or library.get("state") is not None:
                state["source_library"] = library["receipt"]
                state['dropin_receipts'] = receipts
                state = manager._publish(state)
    return {"generation": state["generation"], "updated": changed, "unchanged": skipped,
            "directory": str(inbox), "operators": sum(d["kind"] == "operator" for d in state["descriptors"]),
            "readers": sum(d["kind"] == "reader" for d in state["descriptors"])}


def metadata_candidate(state, package, records, *, version=None):
    from biopipe.metadata_updates import EXECUTION_KEYS, replace_declarations
    old = {d['id']: d for d in state['descriptors'] if d['distribution'] == package}
    if version is not None and version != next((p['version'] for p in state['packages'] if p['name'] == package), None):
        return None
    if not old or set(old) != {d['id'] for d in records}:
        return None
    records = deepcopy(records)
    for d in records:
        before = old[d['id']]
        from biopipe_sdk.dependencies import requirements
        d['dependencies'] = requirements(d.get('dependencies', []))
        if any(d.get(k, []) != before.get(k, []) for k in EXECUTION_KEYS):
            return None
    return replace_declarations(state, records)
