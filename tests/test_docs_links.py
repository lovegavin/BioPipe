"""Keep repository Markdown links resolvable without a docs build step."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), ROOT / "AGENTS.md"]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def test_docs_have_no_broken_relative_links():
    broken = []
    for path in FILES:
        for match in LINK.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            relative = target.split("#", 1)[0].strip()
            if not relative:
                continue
            if not (path.parent / relative).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, "\n".join(broken)
