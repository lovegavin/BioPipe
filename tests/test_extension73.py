"""Hand and dispatch tests for GSEA RNK/CLS/GRP readers."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import ReaderError
from src.reader import pick_reader
from src.reader.readers.cls_reader import ClsReader
from src.reader.readers.grp_reader import GrpReader
from src.reader.readers.rnk_reader import RnkReader


def test_rnk_ranked_list_preserves_order(tmp_path):
    path = tmp_path / "ranked.rnk"
    path.write_text(
        "# generated\nTP53\t1.5\nEGFR\t-2.0\nMYC\t0.25\n",
        encoding="utf-8",
    )
    form = RnkReader().read(path, ["gene", "feature"], {})
    assert form.data.shape == (3, 1)
    assert list(form.labels["gene"]) == ["TP53", "EGFR", "MYC"]
    assert form.labels["feature"]["score"] == 0
    assert form.data[:, 0] == pytest.approx([1.5, -2.0, 0.25])
    assert form.info["n_genes"] == 3
    assert isinstance(pick_reader(path), RnkReader)


def test_rnk_header_and_three_columns(tmp_path):
    path = tmp_path / "ranked3.rnk"
    path.write_text(
        "gene\tdescription\tscore\nTP53\ttumor suppressor\t2.5\nEGFR\treceptor\t-1.0\n",
        encoding="utf-8",
    )
    form = RnkReader().read(
        path,
        ["gene", "feature"],
        {},
        header=True,
        score_column=2,
        feature_label="logFC",
    )
    assert form.labels["feature"]["logFC"] == 0
    assert form.data[:, 0] == pytest.approx([2.5, -1.0])


def test_rnk_rejects_duplicate_and_nonfinite(tmp_path):
    duplicate = tmp_path / "duplicate.rnk"
    duplicate.write_text("A 1\nA 2\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="duplicate gene"):
        RnkReader().read(duplicate, ["gene", "feature"], {})

    bad = tmp_path / "bad.rnk"
    bad.write_text("A nope\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="not numeric"):
        RnkReader().read(bad, ["gene", "feature"], {})


def test_cls_phenotype_encodes_classes(tmp_path):
    path = tmp_path / "pheno.cls"
    path.write_text(
        "6 2 1\n# A B\n0 0 1 1 0 1\n",
        encoding="utf-8",
    )
    form = ClsReader().read(path, ["sample", "feature"], {})
    assert form.data.shape == (6, 1)
    assert list(form.labels["sample"]) == [f"S{i}" for i in range(1, 7)]
    encoder = form.info["encoders"]["feature"]["class"]
    assert encoder.mapping == {"A": 0, "B": 1}
    assert form.data[:, 0].tolist() == [0, 0, 1, 1, 0, 1]
    assert form.info["classes"] == ["A", "B"]
    assert isinstance(pick_reader(path), ClsReader)


def test_grp_phenotype_and_dispatch(tmp_path):
    path = tmp_path / "pheno.grp"
    path.write_text(
        "4 2\n# WT MUT\n0\n1\n0\n1\n",
        encoding="utf-8",
    )
    form = GrpReader().read(path, ["sample", "feature"], {})
    assert form.data.shape == (4, 1)
    encoder = form.info["encoders"]["feature"]["class"]
    assert encoder.mapping == {"WT": 0, "MUT": 1}
    assert form.data[:, 0].tolist() == [0, 1, 0, 1]
    assert isinstance(pick_reader(path), GrpReader)


def test_phenotype_rejects_bad_counts_and_indices(tmp_path):
    bad_count = tmp_path / "bad_count.cls"
    bad_count.write_text("6 2\n# A B\n0 0 1 1 0\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="expected 6 sample class indices"):
        ClsReader().read(bad_count, ["sample", "feature"], {})

    bad_index = tmp_path / "bad_index.grp"
    bad_index.write_text("3 2\n# A B\n0\n2\n1\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="outside"):
        GrpReader().read(bad_index, ["sample", "feature"], {})

    no_names = tmp_path / "no_names.cls"
    no_names.write_text("3 2\nA B\n0 1 0\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="must start with"):
        ClsReader().read(no_names, ["species", "feature"], {})


def test_phenotype_feature_label_and_encoder_override(tmp_path):
    path = tmp_path / "pheno.cls"
    path.write_text("3 1\n# case\n0 0 0\n", encoding="utf-8")
    form = ClsReader().read(
        path,
        ["sample", "feature"],
        {},
        feature_label="condition",
        encoders={"condition": "labelencoder"},
    )
    assert "condition" in form.labels["feature"]
    assert form.info["encoders"]["feature"]["condition"].mapping == {"case": 0}
    assert np.all(form.data == 0)
