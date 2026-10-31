import numpy as np

from src.core import Form
from src.reader import pick_reader
from src.reader.readers.chain_reader import ChainReader
from src.reader.readers.maf_reader import MafReader
from src.task.step.steps.min_max_scale import MinMaxScaleStep
from src.task.step.steps.softmax import SoftmaxStep
from src.task.step.steps.ttest_one_sample import TTestOneSampleStep
from src.task.step.steps.ttest_paired import TTestPairedStep
from src.task.step.steps.umap import UmapStep
from src.task.step.steps.zscore import ZscoreStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels, {"missing_code": np.nan})
    value.validate()
    return value


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _matrix(n=24, p=8):
    rng = np.random.default_rng(31)
    return _form(
        rng.normal(size=(n, p)),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)},
         "feature": {f"f{i}": i for i in range(p)}},
    )


def _grouped(per_group=6, p=3):
    n = per_group * 2
    rng = np.random.default_rng(37)
    features = _form(
        rng.normal(size=(p, n)),
        ["feature", "sample"],
        {"feature": {f"g{i}": i for i in range(p)},
         "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        np.asarray([[i // per_group] for i in range(n)], dtype=object),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        dtype=object,
    )
    return features, meta


def test_umap_projection():
    out, export = _run(UmapStep(), {"n_components": 2, "n_neighbors": 5, "random_state": 0}, [_matrix()])
    assert out.data.shape == (24, 2)
    assert out.dims == ["sample", "component"]
    assert out.labels["component"] == {"UMAP1": 0, "UMAP2": 1}
    assert np.isfinite(out.data).all()
    assert export["n_samples"] == 24


def test_paired_t_test():
    features, meta = _grouped()
    out, export = _run(TTestPairedStep(), {"group_label": "group"}, [features, meta])
    assert out.data.shape == (3, 2)
    assert out.labels["statistic"] == {"T": 0, "P": 1}
    assert np.isfinite(out.data).all()
    assert export["n_groups"] == 2


def test_one_sample_t_test():
    out, export = _run(TTestOneSampleStep(), {"popmean": 0.0}, [_matrix(n=12, p=4)])
    assert out.data.shape == (4, 2)
    assert out.labels["statistic"] == {"T": 0, "P": 1}
    assert np.isfinite(out.data).all()
    assert export["popmean"] == 0.0


def test_scalers_and_softmax():
    matrix = _matrix(n=8, p=4)
    z, _ = _run(ZscoreStep(), {"dim": "sample"}, [matrix])
    assert z.data.shape == matrix.data.shape
    assert np.allclose(z.data.mean(axis=0), 0.0, atol=1e-5)
    assert np.allclose(z.data.std(axis=0, ddof=1), 1.0, atol=1e-5)

    mm, _ = _run(MinMaxScaleStep(), {"dim": "sample"}, [matrix])
    assert np.allclose(mm.data.min(axis=0), 0.0)
    assert np.allclose(mm.data.max(axis=0), 1.0)

    sm, _ = _run(SoftmaxStep(), {"dim": "sample"}, [matrix])
    assert np.allclose(sm.data.sum(axis=0), 1.0, atol=1e-6)


def test_maf_reader(tmp_path):
    path = tmp_path / "sample.maf"
    path.write_text(
        "#version 2.4\n"
        "Hugo_Symbol\tChromosome\tStart_Position\tVariant_Type\n"
        "TP53\t17\t100\tSNP\n"
        "EGFR\t7\t200\tDEL\n"
        "KRAS\t12\t300\tSNP\n",
        encoding="utf-8",
    )
    form = MafReader().read(path, ["variant", "field"], {})
    assert form.data.shape == (3, 4)
    assert form.labels["field"]["Hugo_Symbol"] == 0
    assert form.labels["variant"]["variant:0"] == 0
    assert type(pick_reader(path)).__name__ == "MafReader"


def test_chain_reader(tmp_path):
    path = tmp_path / "sample.chain"
    path.write_text(
        "chain 100 chr1 1000 + 10 20 chr2 2000 + 30 40 1\n"
        "10 0 0\n"
        "chain 50 chr3 500 + 0 10 chr4 600 + 5 15 2\n"
        "5 0 0\n",
        encoding="utf-8",
    )
    form = ChainReader().read(path, ["alignment", "field"], {})
    assert form.data.shape == (2, 12)
    assert form.labels["field"]["score"] == 0
    assert form.labels["field"]["tName"] == 1
    assert form.labels["alignment"]["chain:0"] == 0
    assert type(pick_reader(path)).__name__ == "ChainReader"
