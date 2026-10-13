"""Versioned local plugin installations and metadata-only Studio discovery.

Only worker/probe processes import plugin Python. Each successful installation
creates a new environment generation; running jobs retain their original one.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

from packaging.utils import canonicalize_name
from biopipe_sdk.protocol import describe_operator, describe_reader, validate_extension
from src.web.storage import FileLock, atomic_json
from biopipe.packages import bundled_state, owns_legacy_id


def active_descriptors(state):
    enabled = {p["name"] for p in state["packages"] if p.get("enabled", True)}
    return [d for d in state["descriptors"] if d["distribution"] in enabled]

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {"biopipe.operators": "operator", "biopipe.readers": "reader"}


def run_process(args, *, timeout=180, env=None):
    result = subprocess.run(list(map(str, args)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout)[-6000:])
    return result.stdout


def entry_descriptors():
    """Run only in an isolated probe/worker, never in a GUI HTTP process."""
    from src.task.step.base import Step
    from src.reader.base import Reader
    records = []
    for group, kind in GROUPS.items():
        for entry in metadata.entry_points(group=group):
            cls = entry.load()
            validate_extension(cls, kind)
            base = Step if kind == "operator" else Reader
            if not isinstance(cls, type) or not issubclass(cls, base):
                raise ValueError(f"{entry.value} must subclass {base.__name__}")
            if not cls.output_contract or (kind == "operator" and cls.input_contracts is None):
                raise ValueError(f"{entry.value} must declare its input/output contracts")
            descriptor = describe_operator(cls) if kind == "operator" else describe_reader(cls())
            dist = entry.dist
            package_name = canonicalize_name(dist.metadata["Name"])
            if "." not in descriptor["id"] and not owns_legacy_id(package_name, descriptor["id"]):
                raise ValueError("Plugin IDs must be namespaced, for example lab.scale")
            manifest = dist.read_text("biopipe.json")
            if manifest is not None:
                from biopipe_sdk.protocol import PackageDescriptor
                manifest = json.loads(manifest)
                manifest.setdefault("name", canonicalize_name(manifest.get("package", package_name)))
                PackageDescriptor.model_validate(manifest)
                if manifest['name'] != package_name or manifest['version'] != dist.version:
                    raise ValueError("Package manifest identity differs from wheel metadata")
                declared = {item["id"]: item for item in manifest["descriptors"]}
                if declared.get(descriptor["id"]) != descriptor:
                    raise ValueError(f"Wheel descriptor differs from implementation: {descriptor['id']}")
            descriptor["distribution"] = canonicalize_name(dist.metadata["Name"])
            descriptor["package_version"] = dist.version
            records.append(descriptor)
    ids = [item["id"] for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Two plugin entry points declare the same ID")
    return records


def load_runtime(lock):
    """Register plugins in a fresh worker against a frozen installation lock."""
    from src.task.step import STEPS
    from src.reader import READERS
    import importlib
    if lock.get("package_protocol_version"):
        STEPS.clear()
        READERS.clear()
    for descriptor in active_descriptors(lock):
        module, name = descriptor["entry_point"].split(":", 1)
        cls = getattr(importlib.import_module(module), name)
        validate_extension(cls, descriptor["kind"])
        actual = describe_operator(cls) if descriptor["kind"] == "operator" else describe_reader(cls())
        if (actual["id"] != descriptor["id"] or actual["version"] != descriptor["version"]
                or actual["resources"] != descriptor["resources"]):
            raise ValueError(f"Installed implementation differs from lock: {descriptor['id']}")
        if descriptor.get("origin") == "bundled":
            current = next(d for d in bundled_state()["descriptors"] if d["id"] == descriptor["id"])
            if current["implementation"] != descriptor["implementation"]:
                raise ValueError(f"Bundled implementation changed since this graph was pinned: {descriptor['id']}")
        if descriptor["kind"] == "operator":
            if cls.name in STEPS:
                raise ValueError(f"Duplicate operator ID: {cls.name}")
            STEPS[cls.name] = cls
        else:
            READERS.append(cls())


class PluginManager:
    def __init__(self, data_dir):
        self.directory = Path(data_dir) / "plugins"
        self.registry = self.directory / "registry.json"
        self.lock = FileLock(self.directory / ".install.lock", timeout=600)

    def state(self):
        # atomic_json publishes a complete generation. Readers must NOT wait on
        # the installation lock while pip prepares a new environment.
        if not self.registry.exists():
            with self.lock:
                if not self.registry.exists():
                    self._publish({"protocol_version": 1, "package_protocol_version": 1,
                                   **deepcopy(bundled_state()), "bundled_seen": sorted(p["name"] for p in bundled_state()["packages"])})
        value = json.loads(self.registry.read_text(encoding="utf-8"))
        if not value.get("package_protocol_version"):
            with self.lock:
                value = json.loads(self.registry.read_text(encoding="utf-8"))
                if not value.get("package_protocol_version"):
                    self._publish(self._hydrate(value))
                value = json.loads(self.registry.read_text(encoding="utf-8"))
        current = {p["name"]: p for p in bundled_state()["packages"]}
        changed = {p["name"] for p in value["packages"] if p.get("origin") == "bundled"
                   and p["name"] in current and p.get("sha256") != current[p["name"]]["sha256"]}
        # A receipt distinguishes new shipped providers from packages the user
        # removed. Pre-receipt profiles recover that history from snapshots.
        seen = set(value.get("bundled_seen", []))
        if "bundled_seen" not in value:
            seen.update(p["name"] for p in value["packages"])
            for path in (self.directory / "snapshots").glob("*.json"):
                previous = json.loads(path.read_text(encoding="utf-8"))
                seen.update(p["name"] for p in previous.get("packages", []))
        additions = set(current) - seen - {p["name"] for p in value["packages"]}
        if changed or additions or "bundled_seen" not in value:
            with self.lock:
                value = json.loads(self.registry.read_text(encoding="utf-8"))
                additions -= set(value.get("bundled_seen", [])) | {p["name"] for p in value["packages"]}
                value["packages"].extend(deepcopy(current[name]) for name in sorted(additions))
                for package in value["packages"]:
                    if package["name"] in changed and package.get("origin") == "bundled":
                        enabled = package.get("enabled", True)
                        package.update(deepcopy(current[package["name"]]), enabled=enabled)
                installed = {p["name"] for p in value["packages"] if p.get("origin") == "bundled"}
                replacing = (changed & installed) | additions
                value["descriptors"] = [d for d in value["descriptors"] if d["distribution"] not in replacing] + [deepcopy(d) for d in bundled_state()["descriptors"] if d["distribution"] in replacing]
                value["bundled_seen"] = sorted(seen | set(value.get("bundled_seen", [])) | set(current))
                self._publish(value)
        return value

    def _hydrate(self, value):
        value = deepcopy(value)
        if not value.get("package_protocol_version"):
            bundled = deepcopy(bundled_state())
            value["packages"] = bundled["packages"] + value["packages"]
            value["descriptors"] = bundled["descriptors"] + value["descriptors"]
            value["package_protocol_version"] = 1
            value["bundled_seen"] = sorted(p["name"] for p in bundled["packages"])
        return value

    def _publish(self, state):
        state["generation"] = uuid.uuid4().hex
        atomic_json(self.directory / "snapshots" / (state["generation"] + ".json"), state)
        atomic_json(self.registry, state)
        return state

    def manage(self, name, action):
        self.state()  # Initialize/migrate before the lifecycle transaction.
        with self.lock:
            value = self.state()
            package = next((p for p in value["packages"] if p["name"] == name), None)
            if action == "restore":
                bundled = deepcopy(bundled_state())
                original = next((p for p in bundled["packages"] if p["name"] == name), None)
                if original is None:
                    raise ValueError(f"No bundled package named {name}")
                value["packages"] = [p for p in value["packages"] if p["name"] != name] + [original]
                value["descriptors"] = [d for d in value["descriptors"] if d["distribution"] != name] + [d for d in bundled["descriptors"] if d["distribution"] == name]
            elif package is None:
                raise ValueError(f"Package is not installed: {name}")
            elif action in {"enable", "disable"}:
                package["enabled"] = action == "enable"
            elif action == "remove":
                value["packages"] = [p for p in value["packages"] if p["name"] != name]
                value["descriptors"] = [d for d in value["descriptors"] if d["distribution"] != name]
            else:
                raise ValueError("Unknown package action")
            return self._publish(value)

    def extend_catalog(self, catalog):
        return self._catalog(self.state(), catalog)

    def _catalog(self, state, catalog):
        value = {**deepcopy(catalog), "operators": [], "readers": []}
        for descriptor in active_descriptors(state):
            value["operators" if descriptor["kind"] == "operator" else "readers"].append(descriptor)
        value["plugin_generation"] = state["generation"]
        return value

    def snapshot(self, graph):
        state = self.state()
        required = {}
        def visit(current):
            for node in current.nodes:
                if node.kind == "route":
                    visit(node.route.graph)
                for key, item in current.plugin_lock.items():
                    if key in required and required[key] != item:
                        raise ValueError(f"Conflicting plugin versions in one graph: {key}")
                    required[key] = item
        visit(graph)
        if required:
            # Archived generations remain available for saved/pinned graphs.
            candidates = [state]
            candidates.extend(self._hydrate(json.loads(p.read_text(encoding="utf-8"))) for pattern in ("snapshots/*.json", "environments/*/lock.json") for p in sorted(self.directory.glob(pattern)))
            for candidate in candidates:
                descriptors = {item["id"]: item for item in active_descriptors(candidate)}
                if all(key in descriptors and descriptors[key].get("implementation") == item for key, item in required.items()):
                    return candidate
            raise ValueError("Required plugin versions are unavailable; install the original packages")
        return state

    def pin(self, graph):
        state = self.snapshot(graph)
        descriptors = active_descriptors(state)
        graph = graph.model_copy(deep=True)
        for node in graph.nodes:
            if node.kind == "route":
                node.route.graph = self.pin(node.route.graph)
            elif node.kind == "operator":
                for descriptor in descriptors:
                    if descriptor["id"] == node.operator:
                        graph.plugin_lock[descriptor["id"]] = descriptor["implementation"]
            elif node.source:
                # Conservatively pin all installed readers claiming the suffix.
                from src.reader.base import primary_ext
                for descriptor in descriptors:
                    if descriptor["kind"] == "reader" and primary_ext(Path(node.source.path)) in descriptor["extensions"]:
                        graph.plugin_lock[descriptor["id"]] = descriptor["implementation"]
        return graph

    def catalog_for(self, graph, base):
        return self._catalog(self.snapshot(graph), base)

    def install(self, wheel, *, remove=None):
        """Install a wheel transactionally; a failed probe never changes registry."""
        if remove:
            return self.manage(canonicalize_name(remove), "remove")
        self.state()
        with self.lock:
            current = self.state()
            packages = deepcopy(current["packages"])
            if remove:
                packages = [item for item in packages if item["name"] != canonicalize_name(remove)]
                if len(packages) == len(current["packages"]):
                    raise ValueError(f"Plugin package is not installed: {remove}")
            else:
                wheel = Path(wheel).resolve(strict=True)
                if wheel.suffix != ".whl":
                    raise ValueError("Install a built .whl package; use plugin build for a source directory")
                with wheel.open("rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                with zipfile.ZipFile(wheel) as archive:
                    entries = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
                    if len(entries) != 1:
                        raise ValueError("Invalid wheel metadata")
                    from email.parser import BytesParser
                    info = BytesParser().parsebytes(archive.read(entries[0]))
                name = canonicalize_name(info["Name"])
                if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name):
                    raise ValueError("Invalid package name")
                cached = self.directory / "packages" / digest / wheel.name
                cached.parent.mkdir(parents=True, exist_ok=True)
                if not cached.exists():
                    shutil.copy2(wheel, cached)
                packages = [item for item in packages if item["name"] != name]
                packages.append({"protocol_version": 1, "origin": "wheel", "enabled": True,
                                 "name": name, "version": info["Version"], "sha256": digest,
                                 "wheel": str(cached.relative_to(self.directory))})
            generation = uuid.uuid4().hex
            environment = self.directory / "environments" / generation
            environment.mkdir(parents=True)
            # Parent dependencies are inherited read-only and constrained to the
            # active runtime versions. New plugin dependencies live in this venv.
            run_process([sys.executable, "-m", "venv", "--system-site-packages", environment])
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            site_path = Path(run_process([python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"]).strip())
            import sysconfig
            # Process the parent's .pth files too: merely adding its directory
            # loses editable installs and dependencies inherited by that runtime.
            runtime_site = str(Path(sysconfig.get_path("purelib")))
            (site_path / "biopipe-runtime.pth").write_text(
                f"import site; site.addsitedir({runtime_site!r})\n{ROOT}\n", encoding="utf-8")
            protected = {}
            managed = {p["name"] for p in packages}
            for distribution in metadata.distributions():
                name = distribution.metadata["Name"]
                if name and canonicalize_name(name) not in managed:
                    # Match importlib.metadata.version/sys.path precedence when
                    # a parent environment also contains an older distribution.
                    protected.setdefault(canonicalize_name(name), distribution.version)
            constraints = environment / "constraints.txt"
            constraints.write_text("\n".join(f"{name}=={version}" for name, version in sorted(protected.items())), encoding="utf-8")
            wheel_packages = [p for p in packages if p.get("origin") != "bundled"]
            if wheel_packages:
                run_process([python, "-m", "pip", "install", "--disable-pip-version-check", "--constraint", constraints,
                             *[self.directory / p["wheel"] for p in wheel_packages]], timeout=600)
            result_file = environment / "probe.json"
            run_process([python, "-m", "biopipe.plugins", "probe", result_file])
            descriptors = json.loads(result_file.read_text(encoding="utf-8"))
            from src.task import STEPS
            from src.reader import READERS
            base_ids = set(STEPS) | {type(reader).__name__ for reader in READERS}
            for descriptor in descriptors:
                if descriptor["id"] in base_ids and not owns_legacy_id(descriptor["distribution"], descriptor["id"]):
                    raise ValueError(f"Plugin shadows a built-in: {descriptor['id']}")
                package = next((p for p in packages if p["name"] == descriptor["distribution"]), None)
                if package is None:
                    raise ValueError("Unexpected plugin entry point inherited from the base environment")
                descriptor["implementation"] = {"package": package["name"], "version": package["version"], "sha256": package["sha256"]}
                descriptor["origin"] = "wheel"
            if wheel_packages and not descriptors:
                raise ValueError("Package does not expose biopipe.operators or biopipe.readers entry points")
            for package in wheel_packages:
                if not any(d["distribution"] == package["name"] for d in descriptors):
                    raise ValueError(f"No BioPipe entry points in {package['name']}")
                owned = {d["id"] for d in bundled_state()["descriptors"] if d["distribution"] == package["name"]}
                actual = {d["id"] for d in descriptors if d["distribution"] == package["name"]}
                if owned and not owned <= actual:
                    raise ValueError(f"Replacement package must preserve its legacy IDs: {sorted(owned - actual)}")
            bundled_names = {p["name"] for p in packages if p.get("origin") == "bundled"}
            descriptors = [d for d in bundled_state()["descriptors"] if d["distribution"] in bundled_names] + descriptors
            state = {"protocol_version": 1, "package_protocol_version": 1, "generation": generation, "packages": packages, "descriptors": descriptors,
                     "python": str(python.relative_to(self.directory)), "base_dependencies": protected,
                     "bundled_seen": current.get("bundled_seen", [])}
            atomic_json(environment / "lock.json", state)
            atomic_json(self.registry, state)
            return state

    def python_for(self, state):
        return str(self.directory / state["python"]) if state.get("python") else sys.executable


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "probe":
        raise SystemExit("Use: python -m biopipe.plugins probe <output.json>")
    Path(sys.argv[2]).write_text(json.dumps(entry_descriptors(), ensure_ascii=False, allow_nan=False), encoding="utf-8")
