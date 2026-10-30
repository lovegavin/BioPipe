from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path

import pytest

from src.core import ReaderError
from src.reader import pick_reader
from src.reader.readers.mzml_reader import MzmlReader
from src.reader.readers.mztab_reader import MztabReader
from src.reader.readers.mzxml_reader import MzxmlReader


def _read(reader, path, dims, labels):
    result = reader.read(path, dims, labels)
    result.validate()
    return result


def test_mzml_spectrum_summary(tmp_path: Path):
    path = tmp_path / "run.mzML"
    path.write_text(
        "<mzML><run><spectrumList count=\"2\">"
        "<spectrum id=\"scan=1\" index=\"0\" defaultArrayLength=\"3\">"
        "<cvParam accession=\"MS:1000511\" name=\"ms level\" value=\"2\"/>"
        "<scan><cvParam accession=\"MS:1000016\" name=\"scan start time\" value=\"1.5\" unitName=\"minute\"/></scan>"
        "<precursorList><precursor><selectedIonList><selectedIon>"
        "<cvParam name=\"selected ion m/z\" value=\"445.34\"/>"
        "<cvParam name=\"charge state\" value=\"2\"/>"
        "</selectedIon></selectedIonList></precursor></precursorList>"
        "<cvParam name=\"base peak intensity\" value=\"1234.5\"/>"
        "<cvParam name=\"total ion current\" value=\"2345.6\"/>"
        "</spectrum>"
        "<spectrum id=\"scan=2\" index=\"1\" defaultArrayLength=\"0\">"
        "<cvParam name=\"ms level\" value=\"1\"/>"
        "</spectrum>"
        "</spectrumList></run></mzML>",
        encoding="utf-8",
    )
    form = _read(MzmlReader(), path, ["spectrum", "feature"],
                 {"spectrum": "auto", "feature": "builtin"})
    assert form.data.shape == (2, 10)
    f = form.labels["feature"]
    assert form.data[0, f["ms_level"]] == 2
    assert form.data[0, f["retention_time"]] == pytest.approx(90.0)
    assert form.data[0, f["precursor_mz"]] == pytest.approx(445.34)
    assert form.data[0, f["precursor_charge"]] == 2
    assert form.data[0, f["n_peaks"]] == 3
    assert form.data[0, f["base_peak_intensity"]] == pytest.approx(1234.5)
    assert form.data[0, f["total_ion_current"]] == pytest.approx(2345.6)
    assert form.data[1, f["n_peaks"]] == 0


def test_mzxml_scan_summary_and_compressed_peaks(tmp_path: Path):
    peaks = struct.pack(">4f", 100.0, 10.0, 200.0, 20.0)
    encoded = base64.b64encode(peaks).decode("ascii")
    compressed = base64.b64encode(zlib.compress(peaks)).decode("ascii")
    path = tmp_path / "run.mzXML"
    path.write_text(
        "<msRun><scan num=\"1\" msLevel=\"2\" retentionTime=\"PT12.5S\" "
        "lowMz=\"100\" highMz=\"500\" basePeakMz=\"200\" basePeakIntensity=\"300\" "
        "totIonCurrent=\"400\" polarity=\"+\">"
        "<precursorMz precursorCharge=\"2\">250.5</precursorMz>"
        f"<peaks>{encoded}</peaks></scan>"
        "<scan num=\"2\" msLevel=\"1\" polarity=\"-\">"
        f"<peaks compressionType=\"zlib\">{compressed}</peaks></scan>"
        "</msRun>",
        encoding="utf-8",
    )
    form = _read(MzxmlReader(), path, ["scan", "feature"],
                 {"scan": "auto", "feature": "builtin"})
    assert form.data.shape == (2, 11)
    f = form.labels["feature"]
    assert form.data[0, f["ms_level"]] == 2
    assert form.data[0, f["retention_time"]] == pytest.approx(12.5)
    assert form.data[0, f["precursor_mz"]] == pytest.approx(250.5)
    assert form.data[0, f["precursor_charge"]] == 2
    assert form.data[0, f["n_peaks"]] == 2
    assert form.data[0, f["base_peak_mz"]] == 200
    assert form.data[0, f["base_peak_intensity"]] == 300
    assert form.data[0, f["polarity"]] == 1
    assert form.data[1, f["n_peaks"]] == 2
    assert form.data[1, f["polarity"]] == -1


def test_mztab_psm_section_and_auto_selection(tmp_path: Path):
    path = tmp_path / "result.mzTab"
    path.write_text(
        "MTD\tmzTab-version\t1.0.0\n"
        "MTD\tmzTab-mode\tSummary\n"
        "MTD\tmzTab-type\tQuantification\n"
        "PSH\tPSM_ID\tsequence\tcharge\taccession\tspectra_ref\n"
        "PSM\t1\tACDEF\t2\tP1\tms_run[1]:scan=1\n"
        "PSM\t2\tGGK\t3\tP2\tms_run[1]:scan=2\n",
        encoding="utf-8",
    )
    form = _read(MztabReader(), path, ["record", "feature"],
                 {"record": "auto", "feature": "builtin"})
    assert form.data.shape == (2, 5)
    assert form.labels["record"] == {"1": 0, "2": 1}
    assert form.info["section"] == "PSM"
    assert form.info["mztab_version"] == "1.0.0"
    assert form.info["mztab_mode"] == "Summary"
    assert form.info["n_records"] == 2

    with pytest.raises(ReaderError, match="section PEP"):
        MztabReader().read(path, ["record", "feature"],
                           {"record": "auto", "feature": "builtin"}, section="PEP")


def test_mz_readers_pick_reader_dispatch(tmp_path: Path):
    cases = {
        "run.mzML": MzmlReader,
        "run.mzXML": MzxmlReader,
        "result.mzTab": MztabReader,
    }
    for name, cls in cases.items():
        path = tmp_path / name
        path.write_text("", encoding="utf-8")
        assert isinstance(pick_reader(path), cls)
