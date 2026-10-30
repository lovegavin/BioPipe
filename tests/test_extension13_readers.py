"""Hand tests for the 0.20 XML mass-spec readers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.reader import pick_reader
from src.reader.readers.mzdata_reader import MzdataReader
from src.reader.readers.mzidentml_reader import MzidentmlReader
from src.reader.readers.pepxml_reader import PepxmlReader
from src.reader.readers.protxml_reader import ProtxmlReader


MZID = """<?xml version="1.0"?>
<MzIdentML xmlns="http://psidev.info/psi/pi/mzIdentML/1.1">
  <SequenceCollection>
    <Peptide id="pep1"><PeptideSequence>PEPTIDE</PeptideSequence></Peptide>
    <PeptideEvidence id="ev1" peptide_ref="pep1" protein_accession="P1"/>
  </SequenceCollection>
  <DataCollection><AnalysisData><SpectrumIdentificationList>
    <SpectrumIdentificationResult spectrumID="scan=1" id="r1">
      <SpectrumIdentificationItem chargeState="2" experimentalMassToCharge="445.34"
        calculatedMassToCharge="445.2" rank="1" passThreshold="true" peptide_ref="pep1">
        <PeptideEvidenceRef peptideEvidence_ref="ev1"/>
        <cvParam name="Mascot:score" value="42.5"/>
      </SpectrumIdentificationItem>
    </SpectrumIdentificationResult>
  </SpectrumIdentificationList></AnalysisData></DataCollection>
</MzIdentML>
"""

PEPXML = """<?xml version="1.0"?>
<msms_pipeline_analysis><msms_run_summary>
  <spectrum_query spectrum="scan=1" start_scan="1" precursor_neutral_mass="1000.5" assumed_charge="2">
    <search_result><search_hit peptide="PEPTIDE" protein="P1" hit_rank="1"
      calc_neutral_pep_mass="1000.4" massdiff="0.1">
      <search_score name="xcorr" value="2.5"/>
    </search_hit></search_result>
  </spectrum_query>
</msms_run_summary></msms_pipeline_analysis>
"""

MZDATA = """<?xml version="1.0"?>
<mzData><spectrumList count="1"><spectrum id="scan=1">
  <spectrumInstrument msLevel="2" mzRangeStart="100" mzRangeStop="1000">
    <cvParam name="time in minutes" value="1.5"/>
    <cvParam name="positive scan"/>
  </spectrumInstrument>
  <precursor><ion mz="445.34" charge="2"/></precursor>
  <mzArrayBinary><data precision="32" endian="little" length="10"/></mzArrayBinary>
  <cvParam name="number of peaks" value="10"/>
  <cvParam name="base peak intensity" value="500"/>
  <cvParam name="total ion current" value="1000"/>
</spectrum></spectrumList></mzData>
"""

PROTXML = """<?xml version="1.0"?>
<protein_summary><protein_summary_header/>
  <protein_group group_number="1">
    <protein protein_name="P1" percent_coverage="12.5" total_number_peptides="3"
      total_number_distinct_peptides="2" probability="0.99" n_indistinguishable_proteins="1"/>
  </protein_group>
</protein_summary>
"""


def _read(reader, tmp_path: Path, text: str, suffix: str, dims):
    path = tmp_path / f"input{suffix}"
    path.write_text(text, encoding="utf-8")
    form = reader.read(path, dims, {dims[0]: "auto", dims[1]: "builtin"})
    form.validate()
    return form


def test_mzidentml_reader_psm_fields(tmp_path: Path):
    form = _read(MzidentmlReader(), tmp_path, MZID, ".mzid", ["psm", "feature"])
    assert form.data.shape == (1, 9)
    assert form.labels["feature"]["peptide_sequence"] == 6
    encoder = form.info["encoders"]["feature"]["peptide_sequence"]
    assert list(encoder.inverse_transform([0])) == ["PEPTIDE"]
    assert form.data[0, form.labels["feature"]["score"]] == pytest.approx(42.5)
    assert form.data[0, form.labels["feature"]["experimental_mz"]] == pytest.approx(445.34)
    assert form.info["n_spectra"] == 1


def test_pepxml_reader_hit_fields(tmp_path: Path):
    form = _read(PepxmlReader(), tmp_path, PEPXML, ".pepxml", ["spectrum", "feature"])
    assert form.data.shape == (1, 10)
    assert form.data[0, form.labels["feature"]["score"]] == pytest.approx(2.5)
    assert form.data[0, form.labels["feature"]["precursor_neutral_mass"]] == pytest.approx(1000.5)
    assert form.data[0, form.labels["feature"]["assumed_charge"]] == pytest.approx(2.0)


def test_mzdata_reader_spectrum_fields(tmp_path: Path):
    form = _read(MzdataReader(), tmp_path, MZDATA, ".mzdata", ["spectrum", "feature"])
    assert form.data.shape == (1, 11)
    assert form.data[0, form.labels["feature"]["retention_time"]] == pytest.approx(90.0)
    assert form.data[0, form.labels["feature"]["precursor_mz"]] == pytest.approx(445.34)
    assert form.data[0, form.labels["feature"]["n_peaks"]] == pytest.approx(10.0)
    assert form.data[0, form.labels["feature"]["polarity"]] == pytest.approx(0.0)


def test_protxml_reader_protein_fields(tmp_path: Path):
    form = _read(ProtxmlReader(), tmp_path, PROTXML, ".protxml", ["protein", "feature"])
    assert form.data.shape == (1, 7)
    assert form.data[0, form.labels["feature"]["percent_coverage"]] == pytest.approx(12.5)
    assert form.data[0, form.labels["feature"]["total_peptides"]] == pytest.approx(3.0)
    assert form.info["n_records"] == 1


def test_xml20_readers_pick_reader_dispatch(tmp_path: Path):
    cases = {
        "run.mzid": MzidentmlReader,
        "run.pepxml": PepxmlReader,
        "run.mzdata": MzdataReader,
        "run.protxml": ProtxmlReader,
    }
    for name, cls in cases.items():
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert isinstance(pick_reader(path), cls)
