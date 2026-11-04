"""Tests for IMGT numbering."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

from src.task.step.steps.antibody_cdr_kabat import TEMPLATE
from src.task.step.steps.antibody_numbering_imgt import imgt_rows


def test_numbering_covers_every_residue() -> None:
    rows = imgt_rows(TEMPLATE)
    assert len(rows) == len(TEMPLATE)
    assert rows[0]["imgt_code"] == "1"
    assert rows[-1]["imgt_code"] == "128"
    codes = [row["imgt_code"] for row in rows]
    assert len(set(codes)) == len(codes)
    assert all(row["position"] == index + 1 for index, row in enumerate(rows))


def test_regions_follow_the_imgt_ranges() -> None:
    rows = imgt_rows(TEMPLATE)
    cdr = [row for row in rows if row["is_cdr"]]
    assert {row["region"] for row in cdr} == {"CDR1", "CDR2", "CDR3"}
    cdr1 = [row for row in rows if row["region"] == "CDR1"]
    assert cdr1[0]["imgt_number"] == 27
    assert cdr1[-1]["imgt_number"] == 38
    cdr3 = [row for row in rows if row["region"] == "CDR3"]
    assert 105 <= cdr3[0]["imgt_number"] <= 117


def test_unmapped_residues_receive_insertion_codes() -> None:
    rows = imgt_rows(TEMPLATE + "GG")
    assert len(rows) == len(TEMPLATE) + 2
    suffixes = [row["imgt_code"] for row in rows if not row["imgt_code"].isdigit()]
    assert suffixes
    assert all(code[-1].isalpha() for code in suffixes)


def test_oracle_matches_anarci_when_available() -> None:
    abnumber = pytest.importorskip("abnumber")
    try:
        chain = abnumber.Chain(TEMPLATE, scheme="imgt")
    except Exception as error:  # noqa: BLE001 - HMMER database may be absent
        pytest.skip(f"ANARCI numbering unavailable: {error}")
    expected = [str(number).lstrip("H") for number in chain.positions.keys()]
    rows = imgt_rows(TEMPLATE)
    assert [row["imgt_code"] for row in rows] == expected


def test_empty_and_short_sequences_are_rejected() -> None:
    with pytest.raises(StepError, match="must not be empty"):
        imgt_rows("  ")
    with pytest.raises((StepError,), match="does not align"):
        imgt_rows("WWWWWWWWWWWW")


def test_run_round_trip(tmp_path) -> None:
    form = encode_sequences([TEMPLATE], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    ctx.step_params = {"output": "numbering"}
    run(ctx, [{"name": "antibody_numbering_imgt", "inputs": ["sequence"], "params": {"output": "numbering"}}])
    out = ctx["numbering"]
    assert out.data.shape == (len(TEMPLATE), 4)
    assert out.labels["statistic"] == {
        "imgt_number": 0,
        "insertion_index": 1,
        "region_index": 2,
        "is_cdr": 3,
    }
