"""Generate operator/Reader reference pages and machine-readable indexes.

Usage:
    python scripts/build_reference_docs.py
    python scripts/build_reference_docs.py --check

The generated pages are deliberately derived from the live classes and
schemas. Curated prose belongs in docs/reference/notes/<kind>/<name>.md;
the generator appends it and marks the page as reviewed.
"""
from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.reader import READERS  # noqa: E402
from src.task import STEPS  # noqa: E402
from biopipe_sdk.protocol import normalize_schema_titles  # noqa: E402


def _package_map() -> dict[str, str]:
    data = json.loads((ROOT / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))
    result = {}
    for package in data.get("packages", []):
        for descriptor in package.get("descriptors", []):
            result[descriptor["id"]] = package["name"]
    return result


def _tests_for(class_name: str) -> list[str]:
    paths = []
    for folder in ("tests", "tasks"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if class_name in text:
                paths.append(path.relative_to(ROOT).as_posix())
    return sorted(paths)


def _demo_tasks(op_name: str) -> list[str]:
    paths = []
    for path in (ROOT / "tasks").glob("*/task.yaml"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(rf"^\s*-\s*name:\s*{re.escape(op_name)}\s*$", text, re.M):
            paths.append(path.relative_to(ROOT).as_posix())
    return sorted(paths)


def _type_label(field: dict) -> str:
    kind = field.get("type", "any")
    if isinstance(kind, list):
        kind = " / ".join(str(k) for k in kind)
    if field.get("enum"):
        return f"{kind}; enum={field['enum']}"
    return str(kind)


def _table(rows: list[list[str]], headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |")
    return "\n".join(lines)


def _operator_page(name: str, cls, package: str, tests: list[str], demos: list[str]) -> str:
    schema = normalize_schema_titles(cls.parameters_schema or {"type": "object", "properties": {}})
    required = set(schema.get("required", []))
    rows = []
    for key, field in schema.get("properties", {}).items():
        rows.append([
            f"`{key}`", field.get("title", key), _type_label(field),
            str(field.get("default", "")), str(field.get("minimum", "")),
            str(field.get("maximum", "")), "yes" if key in required else "",
            field.get("x-ui-group", "basic"),
        ])
    class_doc = textwrap.dedent(inspect.getdoc(cls) or "").strip()
    module = inspect.getmodule(cls)
    module_doc = textwrap.dedent(inspect.getdoc(module) or "").strip() if module else ""
    doc = class_doc
    if module_doc and module_doc != class_doc:
        doc = f"{class_doc}\n\n--- module documentation ---\n\n{module_doc}".strip()
    inputs = json.dumps(cls.input_contracts or [], ensure_ascii=False, indent=2)
    output = json.dumps(cls.output_contract or {}, ensure_ascii=False, indent=2)
    source = Path(inspect.getsourcefile(cls)).resolve().relative_to(ROOT).as_posix()
    note = ROOT / "docs/reference/notes/operators" / f"{name}.md"
    reviewed = note.is_file()
    parts = [
        f"# {name}",
        "",
        f"> {'Reviewed' if reviewed else 'Auto-generated'} reference. "
        "Verify edge cases against the linked source and tests before publishing an analysis.",
        "",
        f"- Package: `{package}`",
        f"- Source: [`{source}`](../../../{source})",
        "- Tests: " + (", ".join(f"[`{p}`](../../../{p})" for p in tests) or "none found"),
        "- Demo tasks: " + (", ".join(f"[`{p}`](../../../{p})" for p in demos) or "none found"),
        f"- Inputs arity: `{cls.inputs_arity}`; output parameter: `{cls.output_parameter}`",
        "",
        "## Parameters",
        "",
        _table(rows, ["key", "title", "type", "default", "min", "max", "required", "group"])
        if rows else "This operator has no parameters.",
        "",
        "## Input contract",
        "",
        "```json",
        inputs,
        "```",
        "",
        "## Output contract",
        "",
        "```json",
        output,
        "```",
        "",
        "## Processing rules (source docstring)",
        "",
        "```text",
        doc or "No docstring. Read the source and tests before use.",
        "```",
        "",
        "## Minimal YAML skeleton",
        "",
        "```yaml",
        f"- name: {name}",
        "  inputs: [" + ", ".join(f"<input{i + 1}>" for i in range(cls.inputs_arity if isinstance(cls.inputs_arity, int) else 1)) + "]",
        "  params:",
    ]
    if rows:
        for row in rows:
            key = row[0].strip("`")
            parts.append(f"    {key}: <{row[2]}>")
    else:
        parts.append("    {}")
    if cls.output_parameter:
        parts.append(f"    {cls.output_parameter}: <output_name>")
    parts.extend(["```", "", "The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.", ""])
    if reviewed:
        parts.extend(["## Curated notes", "", note.read_text(encoding="utf-8").strip(), ""])
    else:
        parts.extend([
            "## Before using this operator",
            "",
            "This page is generated from the declaration. If the analysis depends on a numerical edge case, "
            "read the linked source and at least one linked test. If the page lacks a caveat you need, add it to "
            f"`docs/reference/notes/operators/{name}.md` and regenerate.",
            "",
        ])
    return "\n".join(parts)


def _reader_page(reader) -> str:
    cls = type(reader)
    schema = normalize_schema_titles(cls.parameters_schema or {"type": "object", "properties": {}})
    required = set(schema.get("required", []))
    rows = []
    for key, field in schema.get("properties", {}).items():
        rows.append([
            f"`{key}`", field.get("title", key), _type_label(field),
            str(field.get("default", "")), "yes" if key in required else "",
        ])
    name = cls.__name__
    source = Path(inspect.getsourcefile(cls)).resolve().relative_to(ROOT).as_posix()
    tests = _tests_for(name)
    note = ROOT / "docs/reference/notes/readers" / f"{name}.md"
    reviewed = note.is_file()
    parts = [
        f"# {name}",
        "",
        f"> {'Reviewed' if reviewed else 'Auto-generated'} reference. "
        "Verify format edge cases against the linked source and tests.",
        "",
        f"- Source: [`{source}`](../../../{source})",
        f"- Extensions: `{', '.join(cls.extensions)}`",
        f"- Compression handled natively: `{cls.handles_compression}`",
        "- Tests: " + (", ".join(f"[`{p}`](../../../{p})" for p in tests) or "none found"),
        "",
        "## File input hints",
        "",
        "```json",
        json.dumps(cls.file_input or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Parameters",
        "",
        _table(rows, ["key", "title", "type", "default", "required"]) if rows else "This Reader has no parameters.",
        "",
        "## Output contract",
        "",
        "```json",
        json.dumps(cls.output_contract or {}, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Processing rules (source docstring)",
        "",
        "```text",
        (textwrap.dedent(inspect.getdoc(cls) or "").strip() or "No docstring."),
        "```",
        "",
    ]
    module = inspect.getmodule(cls)
    module_doc = textwrap.dedent(inspect.getdoc(module) or "").strip() if module else ""
    if module_doc and module_doc != (textwrap.dedent(inspect.getdoc(cls) or "").strip()):
        parts.extend(["### Module documentation", "", "```text", module_doc, "```", ""])
    if reviewed:
        parts.extend(["## Curated notes", "", note.read_text(encoding="utf-8").strip(), ""])
    else:
        parts.extend([
            "## Before using this Reader",
            "",
            "Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. "
            f"Add caveats to `docs/reference/notes/readers/{name}.md` and regenerate.",
            "",
        ])
    return "\n".join(parts)


def build(check: bool = False) -> int:
    packages = _package_map()
    operators = []
    readers = []
    failures = []
    for name, cls in sorted(STEPS.items()):
        tests = _tests_for(cls.__name__)
        demos = _demo_tasks(name)
        page = ROOT / "docs/reference/operators" / f"{name}.md"
        content = _operator_page(name, cls, packages.get(name, "unknown"), tests, demos)
        operators.append({
            "id": name,
            "kind": "operator",
            "title": getattr(cls, "title", None) or name,
            "package": packages.get(name, "unknown"),
            "inputs_arity": cls.inputs_arity,
            "output_parameter": cls.output_parameter,
            "contracts": {"inputs": cls.input_contracts or [], "output": cls.output_contract or {}},
            "parameters_schema": normalize_schema_titles(cls.parameters_schema or {}),
            "source": Path(inspect.getsourcefile(cls)).resolve().relative_to(ROOT).as_posix(),
            "tests": tests,
            "demo_tasks": demos,
            "doc": page.relative_to(ROOT).as_posix(),
            "quality": "reviewed" if (ROOT / "docs/reference/notes/operators" / f"{name}.md").is_file() else "auto",
        })
        if check:
            if not page.is_file() or "## Processing rules" not in page.read_text(encoding="utf-8"):
                failures.append(str(page.relative_to(ROOT)))
        else:
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(content, encoding="utf-8")
    for reader in sorted(READERS, key=lambda item: type(item).__name__):
        cls = type(reader)
        name = cls.__name__
        page = ROOT / "docs/reference/readers" / f"{name}.md"
        if check:
            if not page.is_file() or "## Processing rules" not in page.read_text(encoding="utf-8"):
                failures.append(str(page.relative_to(ROOT)))
        else:
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text(_reader_page(reader), encoding="utf-8")
        readers.append({
            "id": name,
            "kind": "reader",
            "extensions": cls.extensions,
            "file_input": cls.file_input or {},
            "parameters_schema": normalize_schema_titles(cls.parameters_schema or {}),
            "output_contract": cls.output_contract or {},
            "source": Path(inspect.getsourcefile(cls)).resolve().relative_to(ROOT).as_posix(),
            "tests": _tests_for(name),
            "doc": page.relative_to(ROOT).as_posix(),
            "quality": "reviewed" if (ROOT / "docs/reference/notes/readers" / f"{name}.md").is_file() else "auto",
        })
    if not check:
        ref = ROOT / "docs/reference"
        (ref / "operator_index.json").write_text(json.dumps(operators, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (ref / "reader_index.json").write_text(json.dumps(readers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        readme = """# Reference index

`operator_index.json` and `reader_index.json` are generated from the live
classes and schemas. Read the JSON index first, then only the pages for the
operators you are considering. The workflow is in `../route_sop.md`; the
LLM and human entry points are `../llm_guide.md` and `../user_guide.md`.

Pages marked **Auto-generated** are derived from the declaration. If a
numerical/format edge case matters, read the linked source and tests, or add
a curated note under `notes/operators/` or `notes/readers/` and regenerate.

```bash
python scripts/build_reference_docs.py          # write pages/indexes
python scripts/build_reference_docs.py --check  # CI: pages must exist
```
"""
        (ref / "README.md").write_text(readme, encoding="utf-8")
        print(f"wrote {len(operators)} operator pages, {len(readers)} Reader pages")
    if failures:
        print("missing/stale reference pages:\n" + "\n".join(failures), file=sys.stderr)
        return 1
    print("reference pages OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return build(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
