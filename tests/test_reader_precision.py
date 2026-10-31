"""Text readers must not silently round genomic coordinates through float32."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.reader import read_source

# Above float32's exact-integer range (2**24); routine for human chromosomes.
START = 100_000_001
END = 100_000_010


def _value(form, field: str) -> float:
    return float(form.data[0, form.labels["field"][field]])


def test_bed_coordinates_are_exact(tmp_path):
    path = tmp_path / "coords.bed"
    path.write_text(f"chr1\t{START}\t{END}\n", encoding="utf-8")
    form = read_source(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert form.data.dtype == np.float64
    assert _value(form, "chromStart") == START
    assert _value(form, "chromEnd") == END


def test_gff3_coordinates_are_exact(tmp_path):
    path = tmp_path / "coords.gff3"
    path.write_text(
        f"chr1\tsrc\tgene\t{START}\t{END}\t.\t+\t.\tID=gene1\n",
        encoding="utf-8",
    )
    form = read_source(path, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert form.data.dtype == np.float64
    assert _value(form, "start") == START
    assert _value(form, "end") == END


def test_gtf_coordinates_are_exact(tmp_path):
    path = tmp_path / "coords.gtf"
    path.write_text(
        f'chr1\tsrc\tgene\t{START}\t{END}\t.\t+\t.\tgene_id "gene1";\n',
        encoding="utf-8",
    )
    form = read_source(path, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert form.data.dtype == np.float64
    assert _value(form, "start") == START
    assert _value(form, "end") == END


def test_csv_coordinate_column_is_exact(tmp_path):
    path = tmp_path / "coords.csv"
    path.write_text(f"pos,value\n{START},1\n{END},2\n", encoding="utf-8")
    form = read_source(
        path,
        ["sample", "feature"],
        {"sample": "auto", "feature": "builtin"},
    )
    assert form.data.dtype == np.float64
    pos = form.labels["feature"]["pos"]
    assert list(form.data[:, pos]) == [START, END]


def test_parquet_coordinate_column_is_exact(tmp_path):
    pytest.importorskip("pyarrow")
    path = tmp_path / "coords.parquet"
    pd.DataFrame({"pos": [START, END], "value": [1.0, 2.0]}).to_parquet(path, index=False)
    form = read_source(
        path,
        ["sample", "feature"],
        {"sample": "auto", "feature": "builtin"},
    )
    assert form.data.dtype == np.float64
    pos = form.labels["feature"]["pos"]
    assert list(form.data[:, pos]) == [START, END]


def test_small_numeric_tables_stay_float32(tmp_path):
    path = tmp_path / "small.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    form = read_source(path, ["sample", "feature"], {"sample": "auto", "feature": "builtin"})
    assert form.data.dtype == np.float32


def test_interval_merge_preserves_large_coordinates(tmp_path):
    from biopipe_sdk.testing import run_operator
    from src.task.step.steps.interval_merge import IntervalMergeStep

    path = tmp_path / "overlap.bed"
    path.write_text(
        f"chr1\t{START}\t{START + 9}\n"
        f"chr1\t{START + 4}\t{END + 10}\n",
        encoding="utf-8",
    )
    form = read_source(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    out = run_operator(IntervalMergeStep, [form], {"min_overlap": 0})
    stats = out.labels["statistic"]
    assert out.data.dtype == np.float64
    assert int(out.data[0, stats["start"]]) == START
    assert int(out.data[0, stats["end"]]) == END + 10
