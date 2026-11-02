"""Tests for the sequence k-mer enrichment operator."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import fisher_exact

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_kmer_enrichment import (
    benjamini_hochberg,
    enrichment_rows,
    kmer_counts,
)


def _run(tmp_path: Path, query: list[str], background: list[str], **params) -> Context:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["query"] = encode_sequences(query, "sequence", "position", "dna")
    ctx["background"] = encode_sequences(background, "sequence", "position", "dna")
    run(
        ctx,
        [
            {
                "name": "sequence_kmer_enrichment",
                "inputs": ["query", "background"],
                "params": {"output": "enrichment", **params},
            }
        ],
    )
    return ctx


def test_kmer_counts() -> None:
    counts, total = kmer_counts(["ACGTACGT"], 2)
    assert total == 7
    assert dict(counts) == {"AC": 2, "CG": 2, "GT": 2, "TA": 1}
    with pytest.raises(StepError, match="shorter than the k-mer size"):
        kmer_counts(["ACG"], 4)


def test_benjamini_hochberg_matches_hand_calculation() -> None:
    assert benjamini_hochberg([0.01, 0.04, 0.03, 0.005]) == pytest.approx(
        [0.02, 0.04, 0.04, 0.02]
    )
    assert benjamini_hochberg([]) == []


def test_enrichment_rows_match_fisher() -> None:
    query = Counter({"AA": 5, "AC": 1})
    background = Counter({"AC": 4, "AA": 1})
    rows = enrichment_rows(query, background, 6, 5, correction="none")
    first = rows[0]
    assert first["kmer"] == "AA"
    expected = fisher_exact([[5, 1], [1, 4]])[1]
    assert first["p_value"] == pytest.approx(float(expected))
    assert first["log2_enrichment"] > 0
    assert rows[-1]["kmer"] == "AC"
    assert rows[-1]["log2_enrichment"] < 0


def test_runner_enriched_kmer(tmp_path: Path) -> None:
    ctx = _run(tmp_path, ["GGGGGGG"], ["ACGTACGT"], k=2)
    form = ctx["enrichment"]
    assert form.dims == ["kmer", "statistic"]
    assert form.labels["statistic"] == {
        "query_count": 0,
        "background_count": 1,
        "log2_enrichment": 2,
        "p_value": 3,
        "q_value": 4,
    }
    assert list(form.labels["kmer"])[0] == "GG"
    index = form.labels["kmer"]["GG"]
    row = form.data[index]
    assert row[0] == pytest.approx(6.0)
    assert row[1] == pytest.approx(0.0)
    assert row[2] > 0
    assert form.info["n_significant"] >= 1
    assert form.info["query_windows"] == 6
    assert form.info["background_windows"] == 7


def test_runner_uses_bh_correction(tmp_path: Path) -> None:
    ctx = _run(tmp_path, ["AAAAAA"], ["ACGTACGT"], k=2, correction="bh")
    form = ctx["enrichment"]
    index = form.labels["kmer"]["AA"]
    row = form.data[index]
    assert row[4] >= row[3]


def test_validation_errors(tmp_path: Path) -> None:
    with pytest.raises((StepError, ValueError), match="k must be between 2 and 8|minimum"):
        _run(tmp_path, ["AAAA"], ["CCCC"], k=1)
    with pytest.raises((StepError, ValueError), match="k must be between 2 and 8|maximum"):
        _run(tmp_path, ["AAAA"], ["CCCC"], k=9)
    with pytest.raises((StepError, ValueError), match="must be 'bh' or 'none'|bonferroni"):
        _run(tmp_path, ["AAAA"], ["CCCC"], correction="bonferroni")
    with pytest.raises(StepError, match="shorter than the k-mer size"):
        _run(tmp_path, ["AA"], ["CCCC"], k=3)
