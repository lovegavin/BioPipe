"""Refresh the builtin index, or build an independently installable builtin wheel.

python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_packages.py --package biopipe-core --output .tmp/packages
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def refresh():
    from biopipe.registry import maintain
    previous = os.environ.get("BIOPIPE_REGISTRY_MAINTENANCE")
    os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = "1"
    try:
        report = maintain("build", scope="packages")
    finally:
        if previous is None:
            os.environ.pop("BIOPIPE_REGISTRY_MAINTENANCE", None)
        else:
            os.environ["BIOPIPE_REGISTRY_MAINTENANCE"] = previous
    if report["errors"]:
        raise ValueError(json.dumps(report["errors"], ensure_ascii=False))
    from biopipe.packages import bundled_manifest, bundled_state
    bundled_manifest.cache_clear()
    bundled_state.cache_clear()
    return json.loads((ROOT / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))


def build_package(name, output):
    from biopipe import __version__
    from biopipe.packages import bundled_manifest
    from biopipe.developer import build
    package = next((p for p in bundled_manifest()["packages"] if p["name"] == name), None)
    if package is None:
        raise ValueError(f"Unknown bundled package: {name}")
    directory = Path(output).resolve() / name
    if directory.exists():
        raise ValueError(f"Choose an unused output directory: {directory}")
    module = name.replace("-", "_") + "_provider"
    target = directory / module
    target.mkdir(parents=True)
    entries, init = {"operator": [], "reader": []}, ["import json", "from pathlib import Path", "from importlib import import_module",
        "_definitions = json.loads(Path(__file__).with_name('definitions.json').read_text(encoding='utf-8'))"]
    definitions = []
    for i, original in enumerate(package["descriptors"]):
        descriptor = deepcopy(original)
        source_module, clsname = descriptor["entry_point"].split(":")
        source = ROOT / (source_module.replace(".", "/") + ".py")
        # A private namespace lets old and new generations coexist; src remains
        # the stable engine ABI, never overwritten by wheel installation.
        content = source.read_text(encoding="utf-8").replace("src.task.step.steps", module).replace("src.reader.readers", module)
        (target / source.name).write_text(content, encoding="utf-8")
        alias = f"Entry{i}"
        descriptor["entry_point"] = f"{module}.{source.stem}:{clsname}"
        definitions.append(descriptor)
        entries[descriptor["kind"]].append(f'{alias} = "{module}:{alias}"')
    # Shared helpers and delegated readers are implementation dependencies.
    helper_sources = list((ROOT / "src/task/step/steps").glob("_*.py")) + list((ROOT / "src/reader/readers").glob("_*.py"))
    if name == "biopipe-readers":
        helper_sources += list((ROOT / "src/reader/readers").glob("*.py"))
    for source in helper_sources:
        if source.name != "__init__.py" and not (target / source.name).exists():
            (target / source.name).write_text(source.read_text(encoding="utf-8").replace("src.task.step.steps", module).replace("src.reader.readers", module), encoding="utf-8")
    init.extend(["def __getattr__(name):", "    index = int(name[5:]) if name.startswith('Entry') and name[5:].isdigit() else -1",
                 "    if index < 0 or index >= len(_definitions): raise AttributeError(name)",
                 "    d = _definitions[index]", "    module, clsname = d['entry_point'].split(':')",
                 "    cls = getattr(import_module(module), clsname)",
                 "    cls.parameters_schema = d['parameters_schema']", "    cls.legacy_parameters = d.get('legacy_parameters', True)",
                 "    cls._package_descriptor = d", "    return cls"])
    (target / "__init__.py").write_text("\n".join(init) + "\n", encoding="utf-8")
    (target / "definitions.json").write_text(json.dumps(definitions, ensure_ascii=False), encoding="utf-8")
    project = ['[build-system]', 'requires = ["setuptools>=69"]', 'build-backend = "setuptools.build_meta"',
               '[project]', f'name = "{name}"', f'version = "{package["version"]}"', 'requires-python = ">=3.11"',
               f'dependencies = ["biopipe-studio=={__version__}"]', '[tool.setuptools.package-data]', f'{module} = ["definitions.json"]']
    for kind, group in (("operator", "operators"), ("reader", "readers")):
        if entries[kind]:
            project += [f'[project.entry-points."biopipe.{group}"]', *entries[kind]]
    (directory / "pyproject.toml").write_text("\n".join(project) + "\n", encoding="utf-8")
    return build(directory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--package")
    parser.add_argument("--output", type=Path, default=Path("build/packages"))
    args = parser.parse_args()
    if args.refresh:
        refresh()
        print("Builtin package index refreshed")
    if args.package:
        print(json.dumps(build_package(args.package, args.output), indent=2))
