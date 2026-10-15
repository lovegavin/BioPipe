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


def icon_assets(content):
    """Literal image declarations in a single-file drop-in, without importing it."""
    paths = set()
    for node in ast.walk(ast.parse(content)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "icon" for t in targets):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if is_image_icon(value):
                paths.add(value)
    return sorted(paths)


def snapshot_module(source, target):
    digest = hashlib.sha256(snapshot(source, target).encode())
    for relative in icon_assets((target / source.name).read_bytes()):
        path = icon_path(source.parent, relative)
        destination = target / relative.replace("\\", "/")
        digest.update(relative.encode() + snapshot(path, destination.parent).encode())
    return digest.hexdigest()


def single_file_wheel(source, output):
    """No build tool needed for a single module; metadata is read without imports."""
    content = source.read_bytes()
    declarations = []
    for node in ast.parse(content, filename=source.name).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == "BIOPIPE_PLUGIN" for target in targets):
            declarations.append(ast.literal_eval(node.value))
    if len(declarations) > 1:
        raise ValueError("Declare BIOPIPE_PLUGIN only once")
    settings = declarations[0] if declarations else {}
    if not isinstance(settings, dict) or set(settings) - {"name", "version", "dependencies"}:
        raise ValueError("BIOPIPE_PLUGIN accepts name, version and dependencies")
    # Stable across machines, independent of the user's home or absolute path.
    suffix = hashlib.sha256(source.name.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", source.stem.lower()).strip("-") or "operator"
    name = settings.get("name", f"biopipe-dropin-{slug}-{suffix}")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("BIOPIPE_PLUGIN.name must be a Python distribution name")
    name = canonicalize_name(name)
    version = str(Version(str(settings.get("version", "0.1.0"))))
    dependencies = settings.get("dependencies", [])
    if not isinstance(dependencies, list) or any(not isinstance(item, str) or "\n" in item or "\r" in item for item in dependencies):
        raise ValueError("BIOPIPE_PLUGIN.dependencies must be a list of requirement strings")
    from biopipe_sdk.dependencies import source_requirements, source_entries
    module = "biopipe_dropin_" + hashlib.sha256(name.encode()).hexdigest()[:16]
    distribution = name.replace("-", "_").replace(".", "_")
    info = f"{distribution}-{version}.dist-info"
    files = {
        f"{module}/__init__.py": content,
        f"{info}/entry_points.txt": f"[biopipe.modules]\ndropin = {module}\n".encode(),
    }
    per_class = source_entries(content, module)
    if per_class:
        import json
        files[f'{info}/biopipe.entries.json'] = json.dumps(per_class).encode()
    else:
        dependencies = sorted(set(dependencies) | set(source_requirements(content)))
    for relative in icon_assets(content):
        path = icon_path(source.parent, relative)
        files[f"{module}/{relative.replace(chr(92), '/')}"] = path.read_bytes()
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
    with tempfile.TemporaryDirectory(prefix="scan-", dir=staging) as temporary:
        temporary = Path(temporary)
        from biopipe.source_library import prepare
        library = prepare(manager, current, temporary / "library")
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
                    run_process([sys.executable, "-m", "pip", "wheel", "--disable-pip-version-check", "--no-deps",
                                 "--wheel-dir", output, target], timeout=600)
                    built = list(output.glob("*.whl"))
                    if len(built) != 1:
                        raise ValueError("Expected exactly one wheel from the plugin project")
                    wheel = built[0]
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
    return {"generation": state["generation"], "updated": changed, "unchanged": skipped,
            "directory": str(inbox), "operators": sum(d["kind"] == "operator" for d in state["descriptors"]),
            "readers": sum(d["kind"] == "reader" for d in state["descriptors"])}
