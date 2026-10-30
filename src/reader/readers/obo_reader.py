"""Open Biomedical Ontologies (OBO) term reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._table_common import table_form


class OboReader(Reader):
    """Reader for [Term] stanzas in OBO files; output is term x field."""

    output_contract = reader_contract()
    file_input = {"dims": ["term", "field"], "labels": {"term": "auto", "field": "builtin"}}
    extensions = [".obo"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"OBO reader: cannot read {path}: {exc}") from exc
        terms = []
        current = None
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("!"):
                continue
            if line.startswith("["):
                if current:
                    terms.append(current)
                current = {} if line == "[Term]" else None
                continue
            if current is not None and ":" in line:
                key, value = line.split(":", 1)
                current.setdefault(key.strip(), value.strip())
        if current:
            terms.append(current)
        rows = []
        term_ids = []
        for term in terms:
            term_id = term.get("id")
            if not term_id:
                continue
            rows.append([
                term_id,
                term.get("name", ""),
                term.get("namespace", ""),
                1 if term.get("is_obsolete", "").lower() == "true" else 0,
            ])
            term_ids.append(term_id)
        if not rows:
            raise ReaderError(f"OBO reader: no [Term] stanzas with id in {path}")
        df = pd.DataFrame(rows, columns=["id", "name", "namespace", "is_obsolete"])
        return table_form(
            df, dims, labels, "OBO", args.get("encoders", {}),
            row_labels=term_ids,
        )
