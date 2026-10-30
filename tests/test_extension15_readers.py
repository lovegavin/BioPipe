"""Hand tests for the 0.22 FCS and AB1 readers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.reader.readers.ab1_reader import Ab1Reader
from src.reader.readers.fcs_reader import FcsReader


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_fcs_reader_example_matrix_and_metadata():
    form = FcsReader().read(
        FIXTURES / "fcs_example.fcs",
        ["event", "channel"],
        {"event": "auto", "channel": "builtin"},
    )
    form.validate()
    assert form.data.shape == (10000, 8)
    assert list(form.labels["channel"]) == [
        "FSC-H", "SSC-H", "FL1-H", "FL2-H",
        "FL3-H", "FL1-A", "FL4-H", "Time",
    ]
    assert list(form.data[0]) == [382.0, 77.0, 618.0, 0.0, 225.0, 55.0, 286.0, 1.0]
    assert form.labels["event"]["event:1"] == 0
    assert form.info["format"] == "FCS"
    assert form.info["fcs_version"] == "2.0"
    assert form.info["datatype"] == "I"
    assert form.info["byte_order"] == [4, 3, 2, 1]
    assert form.info["n_events"] == 10000
    assert form.info["ranges"][:3] == [1024, 1024, 1024]


def test_fcs_reader_max_events():
    form = FcsReader().read(
        FIXTURES / "fcs_example.fcs",
        ["event", "channel"],
        {"event": "auto", "channel": "builtin"},
        max_events=5,
    )
    assert form.data.shape == (5, 8)
    assert form.info["n_events"] == 5
    assert "event:5" in form.labels["event"]


def test_fcs_reader_rejects_non_fcs(tmp_path: Path):
    path = tmp_path / "not.fcs"
    path.write_bytes(b"not an fcs file")
    with pytest.raises(Exception, match="FCS"):
        FcsReader().read(path, ["event", "channel"], {})


def test_ab1_reader_basecalls_quality_and_trace():
    form = Ab1Reader().read(
        FIXTURES / "ab1_example.ab1",
        ["base", "feature"],
        {"base": "builtin", "feature": "builtin"},
    )
    form.validate()
    assert form.data.shape == (605, 6)
    assert form.info["sequence"].startswith("GGGGCATAAGARTGTTTTTT")
    assert form.info["sequence"][:12] == "GGGGCATAAGAR"
    assert form.info["sample"] == "B11_F"
    assert form.info["model"] == "3730"
    assert form.info["base_order"] == "GATC"
    assert form.labels["base"]["1:G"] == 0
    assert form.data[0].tolist() == [12.0, 3.0, -7.0, 0.0, 13.0, -3.0]
    assert form.data[1].tolist() == [13.0, 12.0, -8.0, 18.0, 5.0, -17.0]


def test_ab1_reader_max_bases():
    form = Ab1Reader().read(
        FIXTURES / "ab1_example.ab1",
        ["base", "feature"],
        {"base": "builtin", "feature": "builtin"},
        max_bases=10,
    )
    assert form.data.shape == (10, 6)
    assert form.info["n_bases"] == 10
    assert form.info["sequence"] == "GGGGCATAAG"


def test_ab1_reader_rejects_non_abif(tmp_path: Path):
    path = tmp_path / "not.ab1"
    path.write_bytes(b"not an abif file")
    with pytest.raises(Exception, match="AB1"):
        Ab1Reader().read(path, ["base", "feature"], {})


def test_fcs_ab1_readers_pick_reader_dispatch():
    from src.reader import pick_reader

    assert isinstance(pick_reader(FIXTURES / "fcs_example.fcs"), FcsReader)
    assert isinstance(pick_reader(FIXTURES / "ab1_example.ab1"), Ab1Reader)
