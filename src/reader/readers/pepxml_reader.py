"""pepXML reader: one search hit per row."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from ._xml20_common import attributes, children, descendants, frame_form, numeric


class PepxmlReader(Reader):
    output_contract = reader_contract()
    file_input = {"dims": ["spectrum", "feature"], "labels": {"spectrum": "auto", "feature": "builtin"}}
    extensions = [".pepxml"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
            "max_hits": {"type": "integer", "minimum": 1, "default": 1000000},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"pepXML reader: cannot parse {path}: {exc}") from exc
        records = []
        row_labels = []
        max_hits = int(args.get("max_hits", 1000000))
        for query in descendants(root, "spectrum_query"):
            attrs = attributes(query)
            spectrum = attrs.get("spectrum") or attrs.get("spectrum_title") or f"spectrum:{len(records)}"
            for search_result in children(query, "search_result"):
                for hit in children(search_result, "search_hit"):
                    if len(records) >= max_hits:
                        break
                    hit_attrs = attributes(hit)
                    score = float("nan")
                    for score_elem in children(hit, "search_score"):
                        score_attrs = attributes(score_elem)
                        name = str(score_attrs.get("name", "")).lower()
                        if name in {"xcorr", "hyperscore", "score", "expect"}:
                            score = numeric(score_attrs.get("value"))
                            if score == score:
                                break
                    records.append({
                        "spectrum": spectrum,
                        "start_scan": numeric(attrs.get("start_scan")),
                        "precursor_neutral_mass": numeric(attrs.get("precursor_neutral_mass")),
                        "assumed_charge": numeric(attrs.get("assumed_charge")),
                        "peptide": hit_attrs.get("peptide", ""),
                        "protein": hit_attrs.get("protein", ""),
                        "hit_rank": numeric(hit_attrs.get("hit_rank")),
                        "calc_neutral_pep_mass": numeric(hit_attrs.get("calc_neutral_pep_mass")),
                        "massdiff": numeric(hit_attrs.get("massdiff")),
                        "score": score,
                    })
                    row_labels.append(f"{spectrum}:{len(records) - 1}")
        return frame_form(records, row_labels, dims, labels, "pepXML", path,
                          args.get("encoders"), {"n_spectra": len({r["spectrum"] for r in records})})
