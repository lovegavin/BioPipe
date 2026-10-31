"""The shipped manifest must stay in lockstep with the source tree.

Every bundled operator and reader has a functional preview and a canonical
category.  Comparing the manifest with a fresh source scan means a new module
cannot be added without rebuilding the registry, and a removed module cannot
linger in the UI.
"""
from __future__ import annotations

import json
from pathlib import Path

from biopipe_sdk.protocol import describe_reader
from src.reader import _discover as discover_readers
from src.task.operator_catalog import build_catalog
from src.task.operator_categories import CANONICAL_CATEGORIES
from src.task.step import _discover as discover_steps

ROOT = Path(__file__).resolve().parents[1]


def _manifest():
    return json.loads((ROOT / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))


def _descriptors(kind):
    return {
        descriptor["id"]: descriptor
        for package in _manifest()["packages"]
        for descriptor in package["descriptors"]
        if descriptor["kind"] == kind
    }


def test_every_source_operator_is_in_the_manifest_with_a_canonical_preview():
    source = discover_steps()
    manifest = _descriptors("operator")
    assert set(source) == set(manifest), "operator source tree and registry are out of sync"
    catalog = {item["name"]: item for item in build_catalog(source)["operators"]}
    assert set(catalog) == set(source)
    for name in source:
        item = catalog[name]
        assert item["category"] == manifest[name]["category"], name
        assert item["category"] in CANONICAL_CATEGORIES, name
        assert str(item.get("title", "")).strip(), name
        assert str(item.get("description", "")).strip(), name
        assert item["parameters_schema"].get("type") == "object", name
    assert len(source) == len(manifest)


def test_every_source_reader_is_in_the_manifest_with_a_preview_and_extensions():
    readers = discover_readers()
    manifest = _descriptors("reader")
    by_id = {describe_reader(reader)["id"]: describe_reader(reader) for reader in readers}
    assert set(by_id) == set(manifest), "reader source tree and registry are out of sync"
    for identifier, item in by_id.items():
        assert item["category"] in CANONICAL_CATEGORIES, identifier
        assert str(item.get("title", "")).strip(), identifier
        assert str(item.get("description", "")).strip(), identifier
        assert item["extensions"], identifier
        assert item["extensions"] == manifest[identifier]["extensions"], identifier
    assert len(readers) == len(manifest)


def test_windows_blocked_readers_are_explicitly_marked():
    readers = {describe_reader(reader)["id"]: describe_reader(reader) for reader in discover_readers()}
    blocked = {name for name, item in readers.items() if item.get("platforms")}
    assert {"BamReader", "BcfReader", "BigWigReader", "CramReader"} <= blocked
