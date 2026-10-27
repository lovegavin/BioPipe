from __future__ import annotations

import json

import h5py
import numpy as np
import pytest

from src.core import ReaderError
from src.reader.readers.biom_reader import BiomReader
from src.reader.readers.gmt_reader import GmtReader
from src.reader.readers.loom_reader import LoomReader


def test_gmt_reader_binary_membership_and_labels(tmp_path):
    path = tmp_path / "sets.gmt"
    path.write_text(
        "A\tdescription\tg1\tg2\tg2\n"
        "B\tsecond\tg2\tg3\n",
        encoding="utf-8",
    )
    form = GmtReader().read(path, ["gene", "gene_set"], {"gene": "builtin", "gene_set": "builtin"})
    assert form.dims == ["gene", "gene_set"]
    assert form.data.shape == (3, 2)
    assert form.data.tolist() == [[1, 0], [1, 1], [0, 1]]
    assert list(form.labels["gene"]) == ["g1", "g2", "g3"]
    assert list(form.labels["gene_set"]) == ["A", "B"]


def test_gmt_reader_rejects_duplicate_set(tmp_path):
    path = tmp_path / "bad.gmt"
    path.write_text("A\td\tg1\nA\td\tg2\n", encoding="utf-8")
    with pytest.raises(ReaderError, match="duplicate"):
        GmtReader().read(path, ["gene", "gene_set"], {})


def test_loom_reader_reads_matrix_and_ids(tmp_path):
    path = tmp_path / "cells.loom"
    data = np.arange(6, dtype=np.float32).reshape(2, 3)
    with h5py.File(path, "w") as handle:
        handle.create_dataset("matrix", data=data)
        handle.create_group("row_attrs").create_dataset("GeneIDs", data=np.array(["g1", "g2"], dtype="S2"))
        handle.create_group("col_attrs").create_dataset("CellID", data=np.array(["c1", "c2", "c3"], dtype="S2"))
    form = LoomReader().read(path, ["gene", "cell"], {"gene": "builtin", "cell": "builtin"})
    assert form.data.shape == (2, 3)
    assert np.array_equal(form.data, data)
    assert list(form.labels["gene"]) == ["g1", "g2"]
    assert list(form.labels["cell"]) == ["c1", "c2", "c3"]


def test_biom_json_and_hdf5_agree(tmp_path):
    rows = [
        {"id": "tax1", "metadata": {"taxonomy": ["Bacteria", "Firmicutes"]}},
        {"id": "tax2", "metadata": {"taxonomy": ["Bacteria", "Bacteroidetes"]}},
    ]
    columns = [{"id": "s1"}, {"id": "s2"}]
    payload = {
        "id": None,
        "format": "Biological Observation Matrix 2.1.0",
        "type": "OTU table",
        "generated_by": "test",
        "date": "2026-10-27",
        "rows": rows,
        "columns": columns,
        "shape": [2, 2],
        "data": [[0, 0, 10.0], [1, 1, 3.0]],
    }
    json_path = tmp_path / "table.biom"
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    json_form = BiomReader().read(json_path, ["sample", "taxon"], {})
    assert json_form.data.tolist() == [[10.0, 0.0], [0.0, 3.0]]
    assert list(json_form.labels["sample"]) == ["s1", "s2"]
    assert list(json_form.labels["taxon"]) == ["tax1", "tax2"]

    h5_path = tmp_path / "table-h5.biom"
    with h5py.File(h5_path, "w") as handle:
        handle.attrs["shape"] = (2, 2)
        sample = handle.create_group("sample")
        sample.create_dataset("ids", data=np.array(["s1", "s2"], dtype="S2"))
        observation = handle.create_group("observation")
        observation.create_dataset("ids", data=np.array(["tax1", "tax2"], dtype="S5"))
        matrix = observation.create_group("matrix")
        matrix.attrs["shape"] = (2, 2)
        matrix.create_dataset("data", data=np.array([10.0, 3.0], dtype=np.float32))
        matrix.create_dataset("indices", data=np.array([0, 1], dtype=np.int32))
        matrix.create_dataset("indptr", data=np.array([0, 1, 2], dtype=np.int32))
    h5_form = BiomReader().read(h5_path, ["sample", "taxon"], {})
    assert h5_form.data.tolist() == [[10.0, 0.0], [0.0, 3.0]]


def test_new_readers_are_registered_and_dispatch(tmp_path):
    from src.reader import pick_reader

    gmt = tmp_path / "sets.gmt"
    gmt.write_text("A\td\tg1\n", encoding="utf-8")
    assert type(pick_reader(gmt)).__name__ == "GmtReader"
    loom = tmp_path / "x.loom"
    with h5py.File(loom, "w") as handle:
        handle.create_dataset("matrix", data=np.zeros((1, 1), dtype=np.float32))
    assert type(pick_reader(loom)).__name__ == "LoomReader"
    biom = tmp_path / "x.biom"
    biom.write_text('{"rows":[{"id":"s"}],"columns":[{"id":"t"}],"shape":[1,1],"data":[[0,0,1]]}', encoding="utf-8")
    assert type(pick_reader(biom)).__name__ == "BiomReader"
