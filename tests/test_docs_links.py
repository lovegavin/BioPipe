"""Keep repository Markdown links resolvable without a docs build step."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), ROOT / "AGENTS.md"]


def prose(path):
    """Markdown lines outside fenced blocks, with inline code spans removed."""
    kept, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            kept.append("".join(line.split("`")[0::2]))
    return chr(10).join(kept)


def links(text):
    """Yield link targets written as [label](target), ignoring plain brackets."""
    for line in text.splitlines():
        start = 0
        while True:
            opened = line.find("[", start)
            if opened < 0:
                break
            closed = line.find("]", opened + 1)
            if closed < 0 or line[closed + 1:closed + 2] != "(":
                start = opened + 1
                continue
            end = line.find(")", closed + 2)
            if end < 0:
                break
            yield line[closed + 2:end]
            start = end + 1


def test_docs_have_no_broken_relative_links():
    broken = []
    for path in FILES:
        for target in links(prose(path)):
            target = target.strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            relative = target.split("#", 1)[0].strip()
            if not relative:
                continue
            if not (path.parent / relative).exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    assert not broken, chr(10).join(broken)
