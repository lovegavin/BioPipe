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
            if kind == "operator" and cls.supports_streaming:
                raise ValueError("Plugin protocol v1 supports full mode; generic streaming needs a separate chunk contract")
            descriptor = describe_operator(cls) if kind == "operator" else describe_reader(cls())
            if "." not in descriptor["id"]:
                raise ValueError("Plugin IDs must be namespaced, for example lab.scale")
            dist = entry.dist
            manifest = dist.read_text("biopipe.json")
            if manifest is not None:
                declared = {item["id"]: item for item in json.loads(manifest)["descriptors"]}
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
    for descriptor in lock.get("descriptors", []):
        module, name = descriptor["entry_point"].split(":", 1)
        cls = getattr(importlib.import_module(module), name)
        actual = describe_operator(cls) if descriptor["kind"] == "operator" else describe_reader(cls())
        if actual["id"] != descriptor["id"] or actual["version"] != descriptor["version"]:
            raise ValueError(f"Installed implementation differs from lock: {descriptor['id']}")
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
            return {"protocol_version": 1, "generation": None, "packages": [], "descriptors": []}
        return json.loads(self.registry.read_text(encoding="utf-8"))

    def extend_catalog(self, catalog):
        state = self.state()
        value = deepcopy(catalog)
        for descriptor in state["descriptors"]:
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
            candidates.extend(json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.directory.glob("environments/*/lock.json")))
            for candidate in candidates:
                descriptors = {item["id"]: item for item in candidate["descriptors"]}
                if all(key in descriptors and descriptors[key].get("implementation") == item for key, item in required.items()):
                    return candidate
            raise ValueError("Required plugin versions are unavailable; install the original packages")
        return state

    def pin(self, graph):
        state = self.snapshot(graph)
        descriptors = state["descriptors"]
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
        value = deepcopy(base)
        state = self.snapshot(graph)
        for descriptor in state["descriptors"]:
            value["operators" if descriptor["kind"] == "operator" else "readers"].append(descriptor)
        return value

    def install(self, wheel, *, remove=None):
        """Install a wheel transactionally; a failed probe never changes registry."""
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
                digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
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
                packages.append({"name": name, "version": info["Version"], "sha256": digest,
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
            (site_path / "biopipe-runtime.pth").write_text(str(Path(sysconfig.get_path("purelib"))) + "\n" + str(ROOT) + "\n", encoding="utf-8")
            protected = {canonicalize_name(d.metadata["Name"]): d.version for d in metadata.distributions()
                         if d.metadata["Name"] and canonicalize_name(d.metadata["Name"]) not in {p["name"] for p in packages}}
            constraints = environment / "constraints.txt"
            constraints.write_text("\n".join(f"{name}=={version}" for name, version in sorted(protected.items())), encoding="utf-8")
            if packages:
                run_process([python, "-m", "pip", "install", "--disable-pip-version-check", "--constraint", constraints,
                             *[self.directory / p["wheel"] for p in packages]], timeout=600)
            result_file = environment / "probe.json"
            run_process([python, "-m", "biopipe.plugins", "probe", result_file])
            descriptors = json.loads(result_file.read_text(encoding="utf-8"))
            from src.task import STEPS
            from src.reader import READERS
            base_ids = set(STEPS) | {type(reader).__name__ for reader in READERS}
            for descriptor in descriptors:
                if descriptor["id"] in base_ids:
                    raise ValueError(f"Plugin shadows a built-in: {descriptor['id']}")
                package = next((p for p in packages if p["name"] == descriptor["distribution"]), None)
                if package is None:
                    raise ValueError("Unexpected plugin entry point inherited from the base environment")
                descriptor["implementation"] = {"package": package["name"], "version": package["version"], "sha256": package["sha256"]}
            if packages and not descriptors:
                raise ValueError("Package does not expose biopipe.operators or biopipe.readers entry points")
            for package in packages:
                if not any(d["distribution"] == package["name"] for d in descriptors):
                    raise ValueError(f"No BioPipe entry points in {package['name']}")
            state = {"protocol_version": 1, "generation": generation, "packages": packages, "descriptors": descriptors,
                     "python": str(python.relative_to(self.directory)), "base_dependencies": protected}
            atomic_json(environment / "lock.json", state)
            atomic_json(self.registry, state)
            return state

    def python_for(self, state):
        return str(self.directory / state["python"]) if state.get("python") else sys.executable


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "probe":
        raise SystemExit("Use: python -m biopipe.plugins probe <output.json>")
    Path(sys.argv[2]).write_text(json.dumps(entry_descriptors(), ensure_ascii=False, allow_nan=False), encoding="utf-8")
