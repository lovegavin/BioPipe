"""HMMER3 domain table (--domtblout) reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_NAMES = [
    "target_name", "target_accession", "target_length", "query_name", "query_accession",
    "query_length", "full_evalue", "full_score", "full_bias", "domain_number", "domain_of",
    "c_evalue", "i_evalue", "domain_score", "domain_bias", "hmm_from", "hmm_to",
    "ali_from", "ali_to", "env_from", "env_to", "accuracy", "description",
]
_NUMERIC = {
    "target_length", "query_length", "full_evalue", "full_score", "full_bias",
    "domain_number", "domain_of", "c_evalue", "i_evalue", "domain_score", "domain_bias",
    "hmm_from", "hmm_to", "ali_from", "ali_to", "env_from", "env_to", "accuracy",
}


class HmmerDomtblReader(Reader):
    """HMMER3 --domtblout reader, one row per domain."""

    output_contract = reader_contract()
    file_input = {"dims": ["domain", "feature"], "labels": {"domain": "auto", "feature": "builtin"}}
    extensions = [".domtblout"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        rows = []
        try:
            handle = path.open("r", encoding="utf-8", errors="replace")
        except OSError as exc:
            raise ReaderError(f"HMMER domtblout reader: cannot read {path}: {exc}") from exc
        with handle:
            for raw in handle:
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                parts = raw.rstrip("\n").split(None, 22)
                if len(parts) < 22:
                    raise ReaderError("HMMER domtblout reader: expected at least 22 columns")
                if len(parts) == 22:
                    parts.append("")
                if len(parts) > 23:
                    parts = parts[:22] + [" ".join(parts[22:])]
                rows.append(parts)
        if not rows:
            raise ReaderError("HMMER domtblout reader: no domain records")
        frame = pd.DataFrame(rows, columns=_NAMES)
        for column in frame.columns:
            if column in _NUMERIC:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return table_form(
            frame, dims, labels, "HMMER domtblout",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"domain:{i}" for i in range(len(frame))],
            info_extra={"format": "HMMER domtblout", "n_domains": len(frame)},
        )
