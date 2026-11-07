import numpy as np
import pytest

from src.core import Form
from src.core.encoding import LabelEncoder
from src.core.errors import StepError
from src.task.step.steps.go_gene_similarity import GoGeneSimilarityStep
from src.task.step.steps.go_ic_profile import GoIcProfileStep
from src.task.step.steps.go_term_similarity import GoTermSimilarityStep

TAB = chr(9)
OBO = """format-version: 1.2

[Term]
id: GO:0000001
name: root
namespace: biological_process

[Term]
id: GO:0000002
name: child a
namespace: biological_process
is_a: GO:0000001 ! root

[Term]
id: GO:0000003
name: child b
namespace: biological_process
is_a: GO:0000001 ! root

[Term]
id: GO:0000004
name: other
namespace: biological_process
is_a: GO:0000002 ! child a
"""

ROWS = [
    ("gene1", "b0001", "gene1", "", "GO:0000002", "PMID:1", "IDA", "", "P", "Protein1", "", "protein", "taxon:511145", "20260101", "GOC", ""),
    ("gene2", "b0002", "gene2", "", "GO:0000003", "PMID:1", "IDA", "", "P", "Protein2", "", "protein", "taxon:511145", "20260101", "GOC", ""),
    ("gene3", "b0003", "gene3", "", "GO:0000004", "PMID:1", "IDA", "", "P", "Protein3", "", "protein", "taxon:511145", "20260101", "GOC", ""),
]
GAF = "!gaf-version: 2.2" + chr(10) + chr(10).join(TAB.join(row) for row in ROWS) + chr(10)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def table_form(columns, fields, row_dim="pair", field_dim="field"):
    encoders = {}
    encoded = []
    for name, values in zip(fields, columns):
        encoder = LabelEncoder()
        encoded.append(encoder.fit_transform(values))
        encoders[name] = encoder
    data = np.column_stack(encoded)
    return Form(
        data,
        dims=[row_dim, field_dim],
        labels={row_dim: {str(index): index for index in range(len(columns[0]))},
                field_dim: {name: index for index, name in enumerate(fields)}},
        info={"encoders": {field_dim: encoders}},
    )


def paths(tmp_path):
    obo = tmp_path / "mini.obo"
    gaf = tmp_path / "mini.gaf"
    obo.write_text(OBO, encoding="utf-8")
    gaf.write_text(GAF, encoding="utf-8")
    return str(obo), str(gaf)


def test_ic_profile_values(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("GO:0000002", "GO:0000003", "GO:0000004")], ["term"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "profile"})
    GoIcProfileStep().run(ctx, [form])
    profile = ctx["profile"]
    assert profile.data[0, 0] == pytest.approx(-np.log2(2 / 3))
    assert profile.data[0, 1] == 2
    assert profile.data[0, 2] == 1
    assert profile.data[2, 0] == pytest.approx(-np.log2(1 / 3))
    assert profile.data[2, 1] == 1


def test_ic_profile_depth_and_parents(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("GO:0000004",)], ["term"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "profile"})
    GoIcProfileStep().run(ctx, [form])
    assert ctx["profile"].data[0, 2] == 2
    assert ctx["profile"].data[0, 3] == 1


def test_term_similarity_values(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("p1", "p2"), ("GO:0000002", "GO:0000002"), ("GO:0000004", "GO:0000003")],
                      ["pair", "term_a", "term_b"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "sim"})
    GoTermSimilarityStep().run(ctx, [form])
    sim = ctx["sim"]
    assert sim.data[0, 0] == pytest.approx(-np.log2(2 / 3))
    assert sim.data[0, 1] == pytest.approx(2 * np.log2(1.5) / (np.log2(1.5) + np.log2(3)))
    assert sim.data[0, 2] == pytest.approx(2 / 3)
    assert sim.data[1, 0] == 0.0
    assert sim.data[1, 2] == pytest.approx(1 / 3)


def test_term_similarity_rejects_unknown(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("p1",), ("GO:9999999",), ("GO:0000002",)], ["pair", "term_a", "term_b"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "sim"})
    with pytest.raises(StepError, match="unknown term"):
        GoTermSimilarityStep().run(ctx, [form])


def test_gene_similarity_best_match(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("p1",), ("gene1",), ("gene3",)], ["pair", "gene_a", "gene_b"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "genes"})
    GoGeneSimilarityStep().run(ctx, [form])
    assert ctx["genes"].data[0, 0] > 0.0
    assert ctx["genes"].data[0, 2] == 0


def test_missing_column_reports_error(tmp_path):
    obo, gaf = paths(tmp_path)
    form = table_form([("GO:0000002",)], ["other"])
    ctx = Ctx({"obo_path": obo, "gaf_path": gaf, "output": "profile"})
    with pytest.raises(StepError, match="column 'term' is missing"):
        GoIcProfileStep().run(ctx, [form])
