"""mzIdentML 1.1/1.2 reader: one PSM per SpectrumIdentificationItem."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from ._xml20_common import attributes, children, descendants, frame_form, numeric, text


_COLUMNS = [
    "spectrum_id", "charge_state", "experimental_mz", "calculated_mz",
    "rank", "pass_threshold", "peptide_sequence", "protein_accession", "score",
]


class MzidentmlReader(Reader):
    provider = 'operon-readers'
    parameters_file = 'mzidentml_reader.MzidentmlReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'MzidentmlReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'MzidentmlReader',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'Reads .mzid, .mzidentml files.',
     'extensions': ['.mzid', '.mzidentml'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['psm', 'feature'], 'labels': {'psm': 'auto', 'feature': 'builtin'}}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ReaderError(f"mzIdentML reader: cannot parse {path}: {exc}") from exc
        peptides = {}
        for elem in descendants(root, "Peptide"):
            attrs = attributes(elem)
            peptide_id = attrs.get("id")
            if peptide_id is None:
                continue
            sequence = ""
            for child in children(elem, "PeptideSequence"):
                sequence = text(child)
                break
            peptides[peptide_id] = sequence
        evidence = {}
        for elem in descendants(root, "PeptideEvidence"):
            attrs = attributes(elem)
            evidence_id = attrs.get("id")
            if evidence_id:
                evidence[evidence_id] = attrs.get("protein_accession") or attrs.get("protein_ref") or ""
        records = []
        row_labels = []
        max_psms = int(args.get("max_psms", 1000000))
        for result in descendants(root, "SpectrumIdentificationResult"):
            result_attrs = attributes(result)
            spectrum_id = result_attrs.get("spectrumID") or result_attrs.get("id") or f"spectrum:{len(records)}"
            for item in children(result, "SpectrumIdentificationItem"):
                if len(records) >= max_psms:
                    break
                attrs = attributes(item)
                peptide_ref = attrs.get("peptide_ref")
                sequence = peptides.get(peptide_ref, "") if peptide_ref else ""
                if not sequence:
                    for child in children(item, "PeptideSequence"):
                        sequence = text(child)
                        break
                accession = ""
                for ref in children(item, "PeptideEvidenceRef"):
                    ref_id = attributes(ref).get("peptideEvidence_ref")
                    if ref_id and ref_id in evidence:
                        accession = evidence[ref_id]
                        break
                score = float("nan")
                for param in children(item, "cvParam"):
                    name = attributes(param).get("name", "").lower()
                    if "score" in name:
                        score = numeric(attributes(param).get("value"))
                        if score == score:
                            break
                records.append({
                    "spectrum_id": spectrum_id,
                    "charge_state": numeric(attrs.get("chargeState")),
                    "experimental_mz": numeric(attrs.get("experimentalMassToCharge")),
                    "calculated_mz": numeric(attrs.get("calculatedMassToCharge")),
                    "rank": numeric(attrs.get("rank")),
                    "pass_threshold": attrs.get("passThreshold", ""),
                    "peptide_sequence": sequence,
                    "protein_accession": accession,
                    "score": score,
                })
                row_labels.append(f"{spectrum_id}:{len(records) - 1}")
        return frame_form(records, row_labels, dims, labels, "mzIdentML", path,
                          args.get("encoders"), {"n_spectra": len({r["spectrum_id"] for r in records})})
