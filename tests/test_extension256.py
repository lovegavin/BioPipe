"""Tests for the Kabat numbering operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.antibody_cdr_kabat import TEMPLATE, kabat_regions
from src.task.step.steps.antibody_numbering_kabat import numbering_rows


def test_numbering_covers_every_residue() -> None:
    rows, spans = numbering_rows(TEMPLATE)
    assert len(rows) == len(TEMPLATE)
    assert rows[0]["kabat_number"] == 1
    numbers = [row["kabat_number"] for row in rows]
    assert numbers == sorted(numbers)
    codes = [row["kabat_code"] for row in rows]
    assert len(set(codes)) == len(codes)
    assert set(spans) == {"FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4"}


def test_cdr_rows_match_the_region_spans() -> None:
    rows, spans = numbering_rows(TEMPLATE)
    expected = sum(
        end - start + 1
        for name, start, end, _residues in kabat_regions(TEMPLATE)
        if name.startswith("CDR")
    )
    cdr_rows = [row for row in rows if row["is_cdr"]]
    assert len(cdr_rows) == expected
    assert {row["region"] for row in cdr_rows} == {"CDR1", "CDR2", "CDR3"}
    cdr1_start, cdr1_end = spans["CDR1"]
    assert [row["position"] for row in cdr_rows if row["region"] == "CDR1"] == list(
        range(cdr1_start, cdr1_end + 1)
    )


def test_unmapped_residues_receive_insertion_codes() -> None:
    extended = TEMPLATE + "GG"
    rows, _spans = numbering_rows(extended)
    assert len(rows) == len(extended)
    suffixes = [row["kabat_code"] for row in rows if not row["kabat_code"].isdigit()]
    assert suffixes, "the two extra residues should carry letter suffixes"
    assert all(code[-1].isalpha() for code in suffixes)
    assert all(int(code[:-1]) >= 1 for code in suffixes)


def test_short_sequence_is_rejected() -> None:
    with pytest.raises(StepError, match="too short"):
        numbering_rows("ACDEFGHIK")


def test_empty_sequence_is_rejected() -> None:
    with pytest.raises(StepError, match="sequence must not be empty"):
        numbering_rows("  ")


def test_oracle_matches_anarci_when_available() -> None:
    abnumber = pytest.importorskip("abnumber")
    try:
        chain = abnumber.Chain(TEMPLATE, scheme="kabat")
    except Exception as error:  # noqa: BLE001 - HMMER database may be absent
        pytest.skip(f"ANARCI numbering unavailable: {error}")
    expected = [str(number).lstrip("H") for number in chain.positions.keys()]
    rows, _spans = numbering_rows(TEMPLATE)
    assert [row["kabat_code"] for row in rows] == expected


def test_run_round_trip(tmp_path) -> None:
    form = encode_sequences([TEMPLATE], "sequence", "position", "protein")
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["sequence"] = form
    ctx.step_params = {"output": "numbering"}
    run(
        ctx,
        [
            {
                "name": "antibody_numbering_kabat",
                "inputs": ["sequence"],
                "params": {"output": "numbering"},
            }
        ],
    )
    out = ctx["numbering"]
    assert out.data.shape == (len(TEMPLATE), 4)
    assert out.info["sequence"] == TEMPLATE
    assert out.info["n_residues"] == len(TEMPLATE)
    assert out.info["n_cdr"] > 0
    assert len(out.info["kabat_codes"]) == len(TEMPLATE)
