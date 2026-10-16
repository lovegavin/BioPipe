"""Invariant verification for transform / relational operators."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import Form
from src.reader import read_source
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder

from src.task.step.steps.select import SelectStep
from src.task.step.steps.drop import DropStep
from src.task.step.steps.rename_dim import RenameDimStep
from src.task.step.steps.transpose import TransposeStep
from src.task.step.steps.concat import ConcatStep
from src.task.step.steps.attach_info import AttachInfoStep
from src.task.step.steps.filter_by import FilterByStep
from src.task.step.steps.bin import BinStep
from src.task.step.steps.prioritize import PrioritizeStep
from src.task.step.steps.order_axis import OrderAxisStep
from src.task.step.steps.explode import ExplodeStep
from src.task.step.steps.pivot import PivotStep
from src.task.step.steps.annotate import AnnotateStep
from src.task.step.steps.aggregate import AggregateStep
from src.task.step.steps.join import JoinStep


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:52], str(actual)[:52]))


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


airway = read_source(
    "tasks/rnaseq_de_demo/input/airway_counts.csv",
    ["gene", "sample"],
    {"gene": {"sample": 0}, "sample": "builtin"},
)
meta = read_source(
    "tasks/rnaseq_de_demo/input/airway_colData.csv",
    ["sample", "feature"],
    {"sample": {"feature": 0}, "feature": "builtin"},
)
print(f"airway : {airway.data.shape}, dims={airway.dims}")
print(f"meta   : {meta.data.shape}, dims={meta.dims}")


# ---------------------------------------------------------------- 1 select
section("1. select")
sample_labels = [k for k, _ in sorted(
    airway.labels["sample"].items(), key=lambda kv: kv[1])]
keep = sample_labels[:3]
out = run_operator(SelectStep, [airway],
                   {"dim": "sample", "labels": keep, "output": "out"})
ok = out.data.shape == (airway.data.shape[0], 3)
record("select: 3 columns", ok, f"(33469,3)", out.data.shape)
ok = set(out.labels["sample"].keys()) == set(keep)
record("select: labels = requested", ok, set(keep), set(out.labels["sample"].keys()))
ok = np.allclose(out.data, airway.data[:, [airway.labels["sample"][s] for s in keep]])
record("select: data matches numpy slice", ok, "equal", "equal" if ok else "differ")


# ---------------------------------------------------------------- 2 drop
section("2. drop")
out = run_operator(DropStep, [airway],
                   {"dim": "sample", "labels": keep, "output": "out"})
ref = [airway.labels["sample"][s] for s in sample_labels if s not in keep]
ok = out.data.shape == (airway.data.shape[0], len(ref))
record("drop: shape equals input minus dropped", ok, f"(33469,{len(ref)})", out.data.shape)
ok = np.allclose(out.data, airway.data[:, ref])
record("drop: data matches complement slice", ok, "equal", "equal" if ok else "differ")


# ---------------------------------------------------------------- 3 rename_dim
section("3. rename_dim")
out = run_operator(RenameDimStep, [airway],
                   {"from": "sample", "to": "cell", "output": "out"})
record("rename_dim: dims = ['gene','cell']",
       out.dims == ["gene", "cell"], "['gene','cell']", out.dims)
record("rename_dim: data identical", np.array_equal(out.data, airway.data),
       "identical", "identical" if np.array_equal(out.data, airway.data) else "differ")
record("rename_dim: labels moved",
       out.labels.get("cell") == airway.labels["sample"],
       "equal", "equal" if out.labels.get("cell") == airway.labels["sample"] else "differ")


# ---------------------------------------------------------------- 4 transpose
section("4. transpose")
out = run_operator(TransposeStep, [airway],
                   {"order": ["sample", "gene"], "output": "out"})
record("transpose: shape (n_sample, n_gene)",
       out.data.shape == (airway.data.shape[1], airway.data.shape[0]),
       f"{(8,33469)}", out.data.shape)
record("transpose: data = X.T", np.array_equal(out.data, airway.data.T),
       "identical", "identical" if np.array_equal(out.data, airway.data.T) else "differ")
record("transpose: dims reordered", out.dims == ["sample", "gene"],
       "['sample','gene']", out.dims)


# ---------------------------------------------------------------- 5 concat
section("5. concat")
a = airway.subset_axis("sample", list(range(4)))
b = airway.subset_axis("sample", list(range(4, 8)))
out = run_operator(ConcatStep, [a, b], {"axis": "sample", "output": "out"})
record("concat: shape restored",
       out.data.shape == airway.data.shape, airway.data.shape, out.data.shape)
record("concat: data reconstructed",
       np.array_equal(out.data, airway.data),
       "identical", "identical" if np.array_equal(out.data, airway.data) else "differ")


# ---------------------------------------------------------------- 6 attach_info
section("6. attach_info")
src_form = Form(
    data=meta.data,
    dims=["sample", "feature"],
    labels={"sample": dict(meta.labels["sample"]),
            "feature": dict(meta.labels["feature"])},
    info={"missing_code": np.nan,
          "cell": [f"c_{i}" for i in range(meta.data.shape[0])]},
    axis_info={"sample": ["cell"]},
)
out = run_operator(AttachInfoStep, [airway, src_form],
                   {"fields": ["cell"], "target_dim": "sample", "output": "out"})
record("attach_info: data unchanged", np.array_equal(out.data, airway.data),
       "identical", "identical" if np.array_equal(out.data, airway.data) else "differ")
record("attach_info: info['cell'] = c_0..c_7",
       out.info.get("cell") == [f"c_{i}" for i in range(airway.data.shape[1])],
       "c_0..c_7", "equal" if out.info.get("cell") == [f"c_{i}" for i in range(airway.data.shape[1])] else "differ")
record("attach_info: axis_info gains 'cell'",
       "cell" in out.axis_info.get("sample", []),
       "contains 'cell'", out.axis_info.get("sample", []))


# ---------------------------------------------------------------- 7 filter_by
section("7. filter_by")
qc = Form(
    data=np.array([[100.0], [500.0]], dtype=np.float32),
    dims=["sample", "statistic"],
    labels={"sample": {"s0": 0, "s1": 1}, "statistic": {"score": 0}},
    info={"missing_code": np.nan},
)
base = Form(
    data=np.array([[1, 2], [3, 4], [5, 6]], dtype=np.float32),
    dims=["gene", "sample"],
    labels={"gene": {"g0": 0, "g1": 1, "g2": 2},
            "sample": {"s0": 0, "s1": 1}},
    info={"missing_code": np.nan},
)
out = run_operator(FilterByStep, [base, qc],
                   {"dim": "sample", "rules": [{"field": "score", "min": 200}],
                    "output": "out"})
ok = out.data.shape == (3, 1) and list(out.labels["sample"].keys()) == ["s1"]
record("filter_by: only s1 kept (score >= 200)", ok,
       "(3,1) and ['s1']", f"{out.data.shape} / {list(out.labels['sample'].keys())}")


# ---------------------------------------------------------------- 8 bin
section("8. bin")
bin_in = Form(
    data=np.array([[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]], dtype=np.float32),
    dims=["gene", "value"],
    labels={"gene": {f"g{i}": i for i in range(6)}, "value": {"v": 0}},
    info={"missing_code": np.nan},
)
out = run_operator(BinStep, [bin_in],
                   {"dim": "gene", "bins": 2, "method": "uniform",
                    "value_label": "v", "output": "out"})
ok = out.data.shape[0] == 6
record("bin: 6 rows preserved", ok, 6, out.data.shape[0])
ok = "bin" in out.dims or "bin" in out.labels
record("bin: output has bin axis or label", ok, "yes", out.dims)


# ---------------------------------------------------------------- 9 prioritize
section("9. prioritize")
prio_form = Form(
    data=np.array([[10.0], [20.0], [30.0], [40.0], [50.0]], dtype=np.float32),
    dims=["gene", "value"],
    labels={"gene": {f"g{i}": i for i in range(5)}, "value": {"v": 0}},
    info={"missing_code": np.nan, "score": [0.5, 0.1, 0.9, 0.3, 0.7]},
    axis_info={"gene": ["score"]},
)
out = run_operator(PrioritizeStep, [prio_form],
                   {"dim": "gene", "by": "score", "top_n": 3, "output": "out"})
record("prioritize: kept 3", out.data.shape[0] == 3, 3, out.data.shape[0])
ok = set(out.labels["gene"].keys()) == {"g0", "g2", "g4"}
record("prioritize: top-3 = g0,g2,g4", ok, "{g0,g2,g4}",
       set(out.labels["gene"].keys()))


# ---------------------------------------------------------------- 10 order_axis
section("10. order_axis")
order_form = Form(
    data=np.array([[10.0], [20.0], [30.0], [40.0]], dtype=np.float32),
    dims=["gene", "value"],
    labels={"gene": {f"g{i}": i for i in range(4)}, "value": {"v": 0}},
    info={"missing_code": np.nan, "score": [0.4, 0.1, 0.3, 0.2]},
    axis_info={"gene": ["score"]},
)
out = run_operator(OrderAxisStep, [order_form],
                   {"dim": "gene", "by": "score", "descending": False,
                    "output": "out"})
order = [k for k, _ in sorted(out.labels["gene"].items(), key=lambda kv: kv[1])]
record("order_axis: ascending = g1,g3,g2,g0",
       order == ["g1", "g3", "g2", "g0"], "['g1','g3','g2','g0']", order)
ok = out.data.flatten().tolist() == [20.0, 40.0, 30.0, 10.0]
record("order_axis: values permuted with the axis", ok,
       "[20,40,30,10]", out.data.flatten().tolist())


# ---------------------------------------------------------------- 11 explode
section("11. explode")
explode_form = Form(
    data=np.array([[10.0], [20.0]], dtype=np.float32),
    dims=["gene", "value"],
    labels={"gene": {"g0": 0, "g1": 1}, "value": {"v": 0}},
    info={"missing_code": np.nan, "membership": ["A;B", "B;C"]},
    axis_info={"gene": ["membership"]},
)
out = run_operator(ExplodeStep, [explode_form],
                   {"dim": "gene", "field": "membership", "sep": ";",
                    "output": "out"})
record("explode: 4 rows", out.data.shape[0] == 4, 4, out.data.shape[0])
record("explode: labels A,B,B#2,C",
       set(out.labels["gene"].keys()) == {"A", "B", "B#2", "C"},
       "{A,B,B#2,C}", set(out.labels["gene"].keys()))


# ---------------------------------------------------------------- 12 pivot
section("12. pivot")
enc_a = get_encoder("labelencoder")
enc_b = get_encoder("labelencoder")
enc_a.fit_transform(["A", "A", "B", "B"])
enc_b.fit_transform(["X", "Y", "X", "Y"])
pivot_form = Form(
    data=np.array([
        [0.0, 0.0, 1.0],
        [0.0, 1.0, 2.0],
        [1.0, 0.0, 3.0],
        [1.0, 1.0, 4.0],
    ], dtype=np.float32),
    dims=["row", "field"],
    labels={"row": {f"r{i}": i for i in range(4)},
            "field": {"key_a": 0, "key_b": 1, "val": 2}},
    info={"missing_code": np.nan,
          "encoders": {"field": {"key_a": enc_a, "key_b": enc_b}}},
)
out = run_operator(PivotStep, [pivot_form],
                   {"index_label": "key_a", "columns_label": "key_b",
                    "values_label": "val", "index_name": "A",
                    "columns_name": "B", "agg": "sum", "output": "out"})
# Expected wide matrix: rows A,B; cols X,Y
# A-X=1, A-Y=2, B-X=3, B-Y=4
ok = out.data.shape == (2, 2)
record("pivot: (2,2) output", ok, "(2,2)", out.data.shape)
expected = np.array([[1.0, 2.0], [3.0, 4.0]])
record("pivot: values match hand layout",
       np.allclose(out.data, expected), "[[1,2],[3,4]]", out.data.tolist())


# ---------------------------------------------------------------- 13 annotate
section("13. annotate")
target = Form(
    data=np.array([[10.0], [20.0], [30.0]], dtype=np.float32),
    dims=["variant", "value"],
    labels={"variant": {"v1": 0, "v2": 1, "v3": 2}, "value": {"x": 0}},
    info={"missing_code": np.nan},
)
ref_form = Form(
    data=np.array([[1.0], [2.0]], dtype=np.float32),
    dims=["variant", "field"],
    labels={"variant": {"v1": 0, "v3": 1}, "field": {"score": 0}},
    info={"missing_code": np.nan},
)
out = run_operator(AnnotateStep, [target, ref_form],
                   {"target_dim": "variant", "source_dim": "variant",
                    "fields": ["score"], "output": "out"})
# score should be added as info, parallel to variant, aligned by label.
ok_present = "score" in out.info
scores = out.info.get("score") if ok_present else None
# v1 -> 1.0, v2 -> missing, v3 -> 2.0
ok_values = (
    ok_present
    and np.isclose(scores[0], 1.0)
    and np.isnan(scores[1])
    and np.isclose(scores[2], 2.0)
)
record("annotate: info['score'] present", ok_present, "yes", "yes" if ok_present else "no")
record("annotate: values aligned by label (v1=1, v2=NaN, v3=2)",
       ok_values, "[1,NaN,2]",
       [None if scores is None else scores[i] for i in range(3)])


# ---------------------------------------------------------------- 14 aggregate
section("14. aggregate")
# 4 genes, 2 samples; groups form maps gene -> group
agg_data = Form(
    data=np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]], dtype=np.float32),
    dims=["gene", "sample"],
    labels={"gene": {"g0": 0, "g1": 1, "g2": 2, "g3": 3},
            "sample": {"s0": 0, "s1": 1}},
    info={"missing_code": np.nan},
)
groups_enc = get_encoder("labelencoder")
groups_enc.fit_transform(["A", "A", "B", "B"])
agg_groups = Form(
    data=np.array([[0.0], [0.0], [1.0], [1.0]], dtype=np.float32),
    dims=["gene", "feature"],
    labels={"gene": {"g0": 0, "g1": 1, "g2": 2, "g3": 3},
            "feature": {"grp": 0}},
    info={"missing_code": np.nan,
          "encoders": {"feature": {"grp": groups_enc}}},
)
out = run_operator(AggregateStep, [agg_data, agg_groups],
                   {"dim": "gene", "group_col": "grp", "method": "sum",
                    "output": "out"})
# A: g0+g1 = [4, 6]   B: g2+g3 = [12, 14]
ok_shape = out.data.shape == (2, 2)
record("aggregate: (2 groups, 2 samples)", ok_shape, "(2,2)", out.data.shape)
expected = np.array([[4.0, 6.0], [12.0, 14.0]])
record("aggregate: sums A=[4,6], B=[12,14]",
       np.allclose(out.data, expected), "[[4,6],[12,14]]", out.data.tolist())


# ---------------------------------------------------------------- 15 join
section("15. join")
# Join expects the shared axis as the first dim (sample-major layout).
left = Form(
    data=np.array([[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]], dtype=np.float32),
    dims=["sample", "gene"],
    labels={"sample": {"s0": 0, "s1": 1},
            "gene": {"g0": 0, "g1": 1, "g2": 2}},
    info={"missing_code": np.nan},
)
right = Form(
    data=np.array([[10.0, 30.0, 50.0], [20.0, 40.0, 60.0]], dtype=np.float32),
    dims=["sample", "gene"],
    labels={"sample": {"s0": 0, "s1": 1},
            "gene": {"g0": 0, "g1": 1, "g2": 2}},
    info={"missing_code": np.nan},
)
out = run_operator(JoinStep, [left, right],
                   {"dim": "sample", "how": "inner",
                    "prefix": "r_", "output": "out"})
# Inner join on samples: both have s0, s1 -> 2 sample rows in result,
# each carrying the columns from both sides.
ok_rows = out.data.shape[0] == 2
record("join: 2 sample rows", ok_rows, 2, out.data.shape[0])
record("join: output columns = 6 (3 left + 3 right)",
       out.data.shape[1] == 6, 6, out.data.shape[1])
expected_left = np.array([[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]])
expected_right = np.array([[10.0, 30.0, 50.0], [20.0, 40.0, 60.0]])
# First three columns are left's, next three are right's
ok_data = (np.allclose(out.data[:, :3], expected_left)
           and np.allclose(out.data[:, 3:], expected_right))
record("join: values match hand-built layout",
       ok_data, "left || right",
       "match" if ok_data else "differ")


# ---------------------------------------------------------------- summary
print()
print("=" * 78)
print("Verification summary")
print("=" * 78)
n_pass = sum(1 for _, ok, _, _ in checks if ok)
print(f"{'':4s}{'check':<66s}{'expected':<20s}{'actual':<22s}")
print("-" * 78)
for name, ok, exp, act in checks:
    status = "PASS" if ok else "FAIL"
    print(f"{status:4s}  {name:<64s}  {exp:<18s}  {act:<20s}")
print("-" * 78)
print(f"{n_pass}/{len(checks)} checks passed")
