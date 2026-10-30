"""mzTab 1.0 tab-separated proteomics/metabolomics reader."""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_SECTION_HEADERS = {"PSH": "PSM", "PEH": "PEP", "PRH": "PRT", "SMH": "SML"}
_SECTION_ROWS = {"PSM": "PSM", "PEP": "PEP", "PRT": "PRT", "SML": "SML"}
_ID_COLUMNS = {"PSM": "PSM_ID", "PEP": "PEP_ID", "PRT": "PRT_ACC", "SML": "SML_ID"}
_ORDER = ("PSM", "PEP", "PRT", "SML")


class MztabReader(Reader):
    """One section of an mzTab file as a record x feature table."""

    output_contract = reader_contract()
    file_input = {"dims": ["record", "feature"], "labels": {"record": "auto", "feature": "builtin"}}
    extensions = [".mztab"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
            "section": {"type": "string", "enum": ["auto", "PSM", "PEP", "PRT", "SML"], "default": "auto"},
            "max_records": {"type": "integer", "minimum": 1, "default": 1000000},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise ReaderError(f"mzTab reader: cannot read {path}: {exc}") from exc

        headers: dict[str, list[str]] = {}
        records: dict[str, list[list[str]]] = {name: [] for name in _ORDER}
        metadata: dict[str, str] = {}
        current = None
        for raw in lines:
            line = raw.rstrip("\r\n")
            if not line.strip():
                continue
            fields = line.split("\t")
            code = fields[0]
            if code == "MTD" and len(fields) >= 3:
                metadata[fields[1]] = fields[2]
                continue
            if code == "COM":
                continue
            section = _SECTION_HEADERS.get(code)
            if section is not None:
                headers[section] = fields[1:]
                current = section
                continue
            section = _SECTION_ROWS.get(code)
            if section is not None and current == section:
                records[section].append(fields[1:])
                continue

        requested = str(args.get("section", "auto"))
        if requested == "auto":
            chosen = next((name for name in _ORDER if records[name]), None)
        else:
            chosen = requested
        if chosen is None:
            raise ReaderError("mzTab reader: no data rows in any supported section")
        if chosen not in headers:
            raise ReaderError(f"mzTab reader: section {chosen} has data but no header row")
        if not records[chosen]:
            raise ReaderError(f"mzTab reader: section {chosen} has no records")

        header = headers[chosen]
        width = len(header)
        rows = []
        for fields in records[chosen][: int(args.get("max_records", 1000000))]:
            if len(fields) < width:
                fields = fields + [""] * (width - len(fields))
            elif len(fields) > width:
                raise ReaderError(
                    f"mzTab reader: {chosen} row has {len(fields)} columns, header has {width}"
                )
            rows.append(fields)
        frame = _frame(rows, header)
        id_column = _ID_COLUMNS[chosen]
        if id_column in frame.columns:
            row_labels = [str(value) if str(value).strip() else f"{chosen}:{i}"
                          for i, value in enumerate(frame[id_column])]
        else:
            row_labels = [f"{chosen}:{i}" for i in range(len(frame))]
        return table_form(
            frame, dims, labels, "mzTab",
            encoders_cfg=args.get("encoders") or {},
            row_labels=row_labels,
            info_extra={
                "format": "mzTab",
                "section": chosen,
                "n_records": len(frame),
                "mztab_version": metadata.get("mzTab-version"),
                "mztab_mode": metadata.get("mzTab-mode"),
                "mztab_type": metadata.get("mzTab-type"),
            },
        )


def _frame(rows: list[list[str]], header: list[str]):
    import pandas as pd

    frame = pd.DataFrame(rows, columns=header, dtype=object)
    for column in frame.columns:
        converted = pd.to_numeric(frame[column], errors="coerce")
        # Keep genuinely textual columns (accessions, sequences, null flags)
        # as text; table_form encodes those consistently.
        non_missing = frame[column].map(lambda value: str(value).strip() not in {"", "null", "NaN"}).sum()
        if non_missing and converted.notna().sum() == non_missing:
            frame[column] = converted
    return frame
