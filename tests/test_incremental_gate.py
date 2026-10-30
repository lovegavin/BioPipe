"""Static gates for the strict incremental test workflow.

These tests do not execute operators.  They audit the generated registry and
the reference tree so that a fast incremental run cannot silently accept a
broken descriptor, an undocumented module, or a stale reference page.

``BIPIPE_CHANGED_MODULES`` is set by ``scripts/test_incremental.py``; when it
is absent (for example during the periodic full suite) the module-to-test
mapping check is skipped.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "biopipe" / "builtin_packages.json"
OPERATOR_INDEX = ROOT / "docs" / "reference" / "operator_index.json"
READER_INDEX = ROOT / "docs" / "reference" / "reader_index.json"
DOCS_TESTS = [
    "tests/test_docs_links.py",
    "tests/test_reference_docs.py",
    "tests/test_portability.py",
]


def _descriptors() -> list[dict]:
    data = json.loads(BUNDLE.read_text(encoding="utf-8"))
    return [d for package in data["packages"] for d in package["descriptors"]]


def _type_names(schema: dict) -> list[str]:
    value = schema.get("type")
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _match_type(value, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return True


def _default_issue(key: str, schema: dict):
    if "default" not in schema:
        return None
    value = schema["default"]
    types = _type_names(schema)
    if types and not any(_match_type(value, t) for t in types):
        return f"{key}: default {value!r} does not match type {types}"
    if value is not None and "enum" in schema and value not in schema["enum"]:
        return f"{key}: default {value!r} is not in enum"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return f"{key}: default {value!r} is below minimum"
        if "maximum" in schema and value > schema["maximum"]:
            return f"{key}: default {value!r} is above maximum"
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            return f"{key}: default {value!r} is not above exclusiveMinimum"
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            return f"{key}: default {value!r} is not below exclusiveMaximum"
    return None


def test_parameters_schemas_are_closed_typed_objects():
    problems: list[str] = []
    for descriptor in _descriptors():
        schema = descriptor.get("parameters_schema")
        if not isinstance(schema, dict):
            problems.append(f"{descriptor['id']}: missing parameters_schema")
            continue
        if schema.get("type") != "object":
            problems.append(f"{descriptor['id']}: schema type is not object")
        if schema.get("additionalProperties") is not False:
            problems.append(f"{descriptor['id']}: additionalProperties is not false")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            problems.append(f"{descriptor['id']}: properties is not an object")
            continue
        for key, prop in properties.items():
            if not isinstance(prop, dict):
                problems.append(f"{descriptor['id']}.{key}: property is not an object")
                continue
            if not any(
                marker in prop
                for marker in ("type", "oneOf", "anyOf", "allOf", "$ref", "enum", "const")
            ):
                problems.append(f"{descriptor['id']}.{key}: property has no type/oneOf/enum")
            issue = _default_issue(f"{descriptor['id']}.{key}", prop)
            if issue:
                problems.append(issue)
        for required in schema.get("required", []):
            if required not in properties:
                problems.append(f"{descriptor['id']}: required {required!r} is not a property")
    assert not problems, "\n".join(problems)


def _sibling_disjoint(a: dict, b: dict) -> bool:
    """True when sibling requirements make two readers unambiguous."""
    a_requires = set(a.get("requires_siblings") or [])
    b_excludes = set(b.get("excludes_siblings") or [])
    b_requires = set(b.get("requires_siblings") or [])
    a_excludes = set(a.get("excludes_siblings") or [])
    return bool((a_requires & b_excludes) or (b_requires & a_excludes))


def test_reader_extensions_are_normalized_and_unambiguous():
    problems: list[str] = []
    by_extension: dict[str, list[dict]] = {}
    for descriptor in _descriptors():
        if descriptor.get("kind") != "reader":
            continue
        extensions = descriptor.get("extensions") or []
        if not extensions:
            problems.append(f"{descriptor['id']}: no extensions")
        for extension in extensions:
            if extension != extension.lower():
                problems.append(f"{descriptor['id']}: extension {extension!r} is not lowercase")
            if not extension.startswith("."):
                problems.append(f"{descriptor['id']}: extension {extension!r} lacks a dot")
            by_extension.setdefault(extension.lower(), []).append(descriptor)
        file_input = descriptor.get("file_input") or {}
        dims = file_input.get("dims") or []
        labels = file_input.get("labels") or {}
        if len(dims) != 2:
            problems.append(f"{descriptor['id']}: file_input dims must contain two dims")
        if set(labels) != set(dims):
            problems.append(f"{descriptor['id']}: file_input labels {sorted(labels)} != dims {dims}")
    for extension, entries in by_extension.items():
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                if not _sibling_disjoint(a, b):
                    problems.append(
                        f"{extension}: {a['id']} and {b['id']} both claim it without "
                        "disjoint sibling requirements"
                    )
    assert not problems, "\n".join(problems)


def test_operator_input_contracts_match_arity():
    problems: list[str] = []
    for descriptor in _descriptors():
        if descriptor.get("kind") != "operator":
            continue
        arity = descriptor.get("inputs_arity")
        contracts = descriptor.get("contracts") or {}
        inputs = contracts.get("inputs") or []
        if arity == "*":
            continue
        if not isinstance(arity, int) or arity < 0:
            problems.append(f"{descriptor['id']}: invalid inputs_arity {arity!r}")
        elif arity != len(inputs):
            problems.append(
                f"{descriptor['id']}: inputs_arity {arity} != contract inputs {len(inputs)}"
            )
        output = contracts.get("output") or {}
        needs_output_parameter = bool(descriptor.get("outputs")) or output.get("mode") == "declare"
        if needs_output_parameter and not descriptor.get("output_parameter"):
            problems.append(f"{descriptor['id']}: missing output_parameter")
        if "output" not in contracts:
            problems.append(f"{descriptor['id']}: missing output contract")
    assert not problems, "\n".join(problems)


def test_reference_indexes_equal_registry_and_pages_exist():
    operators = json.loads(OPERATOR_INDEX.read_text(encoding="utf-8"))
    readers = json.loads(READER_INDEX.read_text(encoding="utf-8"))
    registry = _descriptors()
    registry_operators = {d["id"] for d in registry if d.get("kind") == "operator"}
    registry_readers = {d["id"] for d in registry if d.get("kind") == "reader"}
    index_operators = {d["id"] for d in operators}
    index_readers = {d["id"] for d in readers}
    assert registry_operators == index_operators, "operator index does not match registry"
    assert registry_readers == index_readers, "reader index does not match registry"
    problems: list[str] = []
    for entry in operators + readers:
        doc = ROOT / entry["doc"]
        source = ROOT / entry["source"]
        if not doc.is_file():
            problems.append(f"{entry['id']}: missing doc {entry['doc']}")
            continue
        if "## Processing rules" not in doc.read_text(encoding="utf-8"):
            problems.append(f"{entry['id']}: doc lacks Processing rules")
        if not source.is_file():
            problems.append(f"{entry['id']}: missing source {entry['source']}")
    assert not problems, "\n".join(problems)


def _changed_modules() -> list[str]:
    raw = os.environ.get("BIPIPE_CHANGED_MODULES", "")
    return [item for item in raw.split(os.pathsep) if item.strip()]


def test_changed_modules_have_referencing_tests():
    modules = _changed_modules()
    if not modules:
        pytest.skip("no BIPIPE_CHANGED_MODULES; full-suite mode")
    tests = list((ROOT / "tests").glob("test_*.py"))
    texts = {path: path.read_text(encoding="utf-8", errors="replace") for path in tests}
    problems: list[str] = []
    for relative in modules:
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"{relative}: changed module does not exist")
            continue
        if not relative.startswith(("src/task/step/steps/", "src/reader/readers/")):
            continue
        if path.name.startswith("_"):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        stem = path.stem
        classes = re.findall(r"^class\s+(\w+)", source, re.MULTILINE)
        candidates = [
            test for test, text in texts.items()
            if stem in text or any(cls in text for cls in classes)
        ]
        if not candidates:
            problems.append(f"{relative}: no test file references {stem} or {classes}")
            continue
        if relative.startswith("src/reader/readers/"):
            if not any("pick_reader" in texts[test] for test in candidates):
                problems.append(f"{relative}: reader test does not exercise pick_reader")
        else:
            if not any("assert" in texts[test] for test in candidates):
                problems.append(f"{relative}: operator test has no assertions")
    assert not problems, "\n".join(problems)


def test_reference_generator_check() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_reference_docs.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
