"""Versioned local plugin installations and metadata-only Studio discovery.

Only worker/probe processes import plugin Python. Each successful installation
creates a new environment generation; running jobs retain their original one.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
import threading
import time

from packaging.utils import canonicalize_name
from biopipe_sdk.protocol import PROTOCOL_VERSION, catalog_entry
from src.web.storage import FileLock, atomic_json
from biopipe.packages import bundled_manifest, bundled_state, owns_builtin_id


def require_current_state(value):
    if value.get("package_protocol_version") != PROTOCOL_VERSION:
        raise ValueError("This library uses an older protocol. Close Studio and run `biopipe migrate --profile-dir <profile> --apply`; old wheels must be rebuilt for v3.")
    if "bundled_seen" not in value:
        raise ValueError("Incomplete protocol v3 library: missing bundled_seen receipt")
    if any(d.get("protocol_version") != PROTOCOL_VERSION for d in value.get("descriptors", [])):
        raise ValueError("Library contains old descriptors; migrate it before loading")


def active_descriptors(state):
    enabled = {p["name"] for p in state["packages"] if p.get("enabled", True)}
    return [d for d in state["descriptors"] if d["distribution"] in enabled]

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {"biopipe.operators": "operator", "biopipe.readers": "reader"}
process_context = threading.local()


def run_process(args, *, timeout=180, env=None):
    # JSON descriptors contain arbitrary Unicode. Parent and Python child must
    # agree on the wire encoding even on Windows with an ANSI/GBK console locale.
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONIOENCODING"] = "utf-8"
    cancel = getattr(process_context, 'cancel', None)
    options = dict(cwd=ROOT, env=child_env, stdin=subprocess.DEVNULL,
                   text=True, encoding='utf-8', errors='replace',
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if cancel is None:
        result = subprocess.run(list(map(str, args)), capture_output=True, timeout=timeout, **options)
    else:
        if cancel.is_set():
            raise ValueError('Dependency preparation cancelled: Studio is closing')
        with subprocess.Popen(list(map(str, args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options) as child:
            deadline = time.monotonic() + timeout
            try:
                while True:
                    if cancel.is_set() or time.monotonic() >= deadline:
                        raise ValueError('Dependency preparation cancelled or timed out')
                    try:
                        stdout, stderr = child.communicate(timeout=.2)
                        result = subprocess.CompletedProcess(args, child.returncode, stdout, stderr)
                        break
                    except subprocess.TimeoutExpired:
                        continue
            except BaseException:
                import psutil
                descendants = []
                try:
                    descendants = psutil.Process(child.pid).children(recursive=True)
                    for descendant in reversed(descendants):
                        try: descendant.kill()
                        except psutil.Error: pass
                except psutil.Error:
                    pass
                if child.poll() is None: child.kill()
                child.communicate()
                psutil.wait_procs(descendants, timeout=5)
                raise
    if result.returncode:
        # pip writes dependency-conflict details to stdout and its error to stderr.
        raise ValueError((result.stdout + "\n" + result.stderr).strip()[-6000:])
    return result.stdout


def _runtime_class(descriptor, lock):
    if descriptor.get('execution', {}).get('mode') == 'isolated':
        from biopipe.isolation import proxy_step, proxy_reader
        return (proxy_step if descriptor['kind'] == 'operator' else proxy_reader)(descriptor, lock)
    from biopipe_sdk.declarations import load_class
    return load_class(descriptor)


def load_runtime(lock, manifest=None):
    """Register task descriptors without importing their implementations."""
    from src.task.step import STEPS
    from src.reader import READERS
    from biopipe.lazy import reader_proxy
    require_current_state(lock)
    STEPS.clear()
    READERS.clear()
    selected = {s['name'] for s in manifest['steps']} if manifest is not None else None
    for descriptor in active_descriptors(lock):
        factory = lambda d=descriptor: _runtime_class(d, lock)
        if descriptor['kind'] == 'operator':
            if selected is None or descriptor['id'] in selected:
                STEPS.register(descriptor['id'], factory, descriptor)
        else:
            READERS.append(reader_proxy(descriptor, factory))


_DEFAULT_SOURCES = object()


class PluginManager:
    def __init__(self, data_dir, *, source_root=_DEFAULT_SOURCES, manifest_only=None):
        self.directory = Path(data_dir) / "plugins"
        self.managed_sources = source_root is _DEFAULT_SOURCES
        self._source_root = (None if self.managed_sources or source_root is None else Path(source_root).resolve())
        self.manifest_only = self.managed_sources if manifest_only is None else manifest_only
        self.registry = self.directory / "registry.json"
        self.lock = FileLock(self.directory / ".install.lock", timeout=600)

    @property
    def source_root(self):
        if not self.managed_sources:
            return self._source_root
        state = json.loads(self.registry.read_text(encoding="utf-8")) if self.registry.exists() else {}
        receipt = state.get("source_library") or {}
        relative = receipt.get("root", "library/sources/editable")
        root = (self.directory / relative).resolve()
        if not root.is_relative_to((self.directory / "library/sources").resolve()):
            raise ValueError("Library source directory must stay inside the profile")
        return root

    def ensure_source_root(self):
        """Seed editable sources only on an explicit folder/refresh operation."""
        from biopipe.source_library import seed_sources
        with self.lock:
            if self.managed_sources:
                seed_sources(ROOT, self.source_root)
            return self.source_root

    def bundled_state(self):
        """Use one discovery policy for live, restored, and archived catalogs."""
        return bundled_state(manifest_only=True) if self.manifest_only else bundled_state()

    def state(self):
        # atomic_json publishes a complete generation. Readers must NOT wait on
        # the installation lock while pip prepares a new environment.
        bundled = self.bundled_state()
        if not self.registry.exists():
            with self.lock:
                if not self.registry.exists():
                    self._publish({"protocol_version": PROTOCOL_VERSION, "package_protocol_version": PROTOCOL_VERSION,
                                   **deepcopy(bundled), "bundled_seen": sorted(p["name"] for p in bundled["packages"])})
        value = json.loads(self.registry.read_text(encoding="utf-8"))
        require_current_state(value)
        current = {p["name"]: p for p in bundled["packages"]}
        changed = {p["name"] for p in value["packages"] if p.get("origin") == "bundled"
                   and p["name"] in current and p.get("sha256") != current[p["name"]]["sha256"]}
        # Persisted receipt distinguishes new providers from deliberate removals.
        seen = set(value["bundled_seen"])
        additions = set() if value.get("library_detached") else set(current) - seen - {p["name"] for p in value["packages"]}
        if changed or additions:
            with self.lock:
                value = json.loads(self.registry.read_text(encoding="utf-8"))
                additions -= set(value.get("bundled_seen", [])) | {p["name"] for p in value["packages"]}
                value["packages"].extend(deepcopy(current[name]) for name in sorted(additions))
                # The first metadata-only read changes the package digest policy,
                # not its executable identity. Retain declaration overlays and
                # their original audit pins when the compiled code is unchanged.
                policy_only = {p["name"] for p in value["packages"] if self.manifest_only
                               and p["name"] in changed and not p.get("manifest_only")
                               and p.get("origin") == "bundled"
                               and p.get("version") == current[p["name"]]["version"]
                               and p.get("code_sha") == current[p["name"]]["code_sha"]}
                for package in value["packages"]:
                    if package["name"] in changed and package.get("origin") == "bundled":
                        enabled = package.get("enabled", True)
                        package.pop("manifest_only", None)
                        package.update(deepcopy(current[package["name"]]), enabled=enabled)
                installed = {p["name"] for p in value["packages"] if p.get("origin") == "bundled"}
                replacing = ((changed - policy_only) & installed) | additions
                value["descriptors"] = [d for d in value["descriptors"] if d["distribution"] not in replacing] + [deepcopy(d) for d in bundled["descriptors"] if d["distribution"] in replacing]
                value["bundled_seen"] = sorted(seen | set(value.get("bundled_seen", [])) | set(current))
                self._publish(value)
        value["_runtime_root"] = str(self.directory.resolve())
        return value

    def _publish(self, state):
        state["generation"] = uuid.uuid4().hex
        atomic_json(self.directory / "snapshots" / (state["generation"] + ".json"), state)
        atomic_json(self.registry, state)
        return state

    def update_declarations(self, document):
        from biopipe_sdk.declarations import definitions
        from biopipe.metadata_updates import replace_declarations
        self.state()
        with self.lock:
            current = self.state()
            state = replace_declarations(current, definitions(document))
            if state == current:
                return current
            return self._publish(state)

    def manage(self, name, action):
        self.state()  # Initialize/migrate before the lifecycle transaction.
        with self.lock:
            value = self.state()
            package = next((p for p in value["packages"] if p["name"] == name), None)
            if action == "restore":
                bundled = deepcopy(self.bundled_state())
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
            value["operators" if descriptor["kind"] == "operator" else "readers"].append(catalog_entry(descriptor))
        value["plugin_generation"] = state["generation"]
        return value

    def snapshot(self, graph):
        state = self.state()
        from biopipe.pins import graphs, matches, requirements, resolve
        # Avoid opening the archive for an unpinned/current graph. Nested graphs
        # can contain different old builtin pins, so normalize before conflict checks.
        pins = [part.plugin_lock for part in graphs(graph)]
        if not any(pins):
            return state
        try:
            if matches(state, requirements(graph, state=state)):
                return state
        except ValueError:
            pass
        candidates = [state]
        for pattern in ("snapshots/*.json", "environments/*/lock.json"):
            for path in sorted(self.directory.glob(pattern)):
                candidate = json.loads(path.read_text(encoding="utf-8"))
                if candidate.get("package_protocol_version") == PROTOCOL_VERSION:
                    candidate["_runtime_root"] = str(self.directory.resolve())
                    candidates.append(candidate)
        return resolve(graph, candidates, self.bundled_state())

    def pin(self, graph, *, snapshot=None):
        state = self.snapshot(graph) if snapshot is None else snapshot
        descriptors = active_descriptors(state)
        graph = graph.model_copy(deep=True)
        selected = {d['id']: d['implementation'] for d in descriptors}
        graph.plugin_lock = {key: deepcopy(selected.get(key, pin)) for key, pin in graph.plugin_lock.items()}
        for node in graph.nodes:
            if node.kind == "route":
                node.route.graph = self.pin(node.route.graph, snapshot=state)
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
        if Path(wheel).name.lower().endswith(".biopipe-library.zip"):
            from biopipe.library_bundle import install_bundle
            return install_bundle(self, Path(wheel))
        return self.install_many([wheel])

    @property
    def inbox(self):
        path = self.directory / "inbox"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def refresh(self):
        """Explicit, incremental scan; publish the entire batch or nothing."""
        from biopipe.dropins import refresh
        self.state()
        with self.lock:
            self.ensure_source_root()
            return refresh(self, self.state())

    def install_many(self, wheels):
        self.state()
        with self.lock:
            return self._install_many(wheels, self.state())

    def _install_many(self, wheels, current, *, receipts=None, source_library=None, dependencies=(), publish=True):
        # Caller owns the cross-process lock, including source snapshotting.
        packages = deepcopy(current["packages"])
        replacements = set()
        for wheel in wheels:
            wheel = Path(wheel).resolve(strict=True)
            if wheel.suffix.lower() != ".whl":
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
            if name in replacements:
                raise ValueError(f"More than one input supplies package {name}; keep one version in the plugin folder")
            replacements.add(name)
            cached = self.directory / "packages" / digest / wheel.name
            cached.parent.mkdir(parents=True, exist_ok=True)
            if not cached.exists():
                shutil.copy2(wheel, cached)
            previous = next((item for item in packages if item["name"] == name), {})
            packages = [item for item in packages if item["name"] != name]
            packages.append({"protocol_version": PROTOCOL_VERSION, "origin": "wheel", "enabled": previous.get("enabled", True),
                             "name": name, "version": info["Version"], "sha256": digest,
                             "wheel": str(cached.relative_to(self.directory))})
        generation = uuid.uuid4().hex
        from biopipe.install_targets import install
        state = install(self, current, packages, generation, dependencies=dependencies)
        environment = self.directory / "environments" / generation
        source_receipt = deepcopy(source_library if source_library is not None else current.get("source_library", {}))
        if source_library is None:
            # An explicitly installed provider takes precedence over local sources.
            source_receipt["packages"] = [name for name in source_receipt.get("packages", []) if name not in replacements]
        state.update(protocol_version=PROTOCOL_VERSION, package_protocol_version=PROTOCOL_VERSION,
                     dropin_receipts=receipts if receipts is not None else current.get("dropin_receipts", {}),
                     source_library=source_receipt)
        if source_receipt.get('root'):
            state['library_detached'] = True
        atomic_json(environment / "lock.json", state)
        if publish:
            atomic_json(self.registry, state)
        return state

    def python_for(self, state):
        # All v3 generations use the host interpreter with dependency targets.
        return sys.executable
