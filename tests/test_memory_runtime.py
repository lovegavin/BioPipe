"""Real arrays and disk I/O; semantic and failure-safety integration checks."""
import json
from pathlib import Path
import time

import numpy as np
import pytest

from src.core import Form, ContextError, ManifestError
from src.reader.readers._encoder import get_encoder
from src.task import Context, STEPS, load_manifest, run
from src.task.memory import DiskBudgetError, MemoryBudgetError, MemoryConfig
from src.task.memory.planner import LifetimePlan
from src.task.step.steps.describe import DescribeStep


def form(data, info=None):
    return Form(data, ["sample", "feature"],
                {"sample": {f"s{i}": i for i in range(data.shape[0])},
                 "feature": {f"f{i}": i for i in range(data.shape[1])}},
                info or {"missing_code": np.nan})


def context(tmp_path, budget=8, **options):
    return Context(tmp_path, {"sources": {}, "steps": [],
                   "runtime": {"memory": {"budget_mb": budget, "poll_ms": 10000, **options}}})


def events(ctx):
    return [json.loads(line) for line in ctx.memory.event_path.read_text(encoding="utf-8").splitlines()]


def test_lossless_spill_metadata_noncontiguous_and_reload(tmp_path):
    ctx = context(tmp_path)
    data = np.arange(120, dtype=np.int16).reshape(10, 12)[:, ::2]
    original = form(data, {"missing_code": -1, "pos": np.arange(10),
                          "nested": {"tuple": (1, "a"), "nan": np.nan},
                          "encoders": {"feature": {"f0": get_encoder("labelencoder")}}})
    original.axis_info = {"sample": ["pos"]}
    ctx["X"] = original
    entry = ctx.forms.entry("X")
    ctx.forms.spill(entry, "test")
    assert entry.form is None and entry.disk.is_dir()
    restored = ctx["X"]
    np.testing.assert_array_equal(restored.data, original.data)
    assert restored.data.dtype == np.int16 and restored.labels == original.labels
    assert restored.axis_info == original.axis_info
    np.testing.assert_array_equal(restored.info["pos"], original.info["pos"])
    assert restored.info["nested"]["tuple"] == (1, "a")
    assert np.isnan(restored.info["nested"]["nan"])
    assert restored.info["encoders"]["feature"]["f0"].name == original.info["encoders"]["feature"]["f0"].name
    ctx.memory.close("failed")


def test_quota_failure_preserves_unique_copy_and_removes_partial(tmp_path):
    ctx = context(tmp_path, disk_limit_mb=.001)
    value = form(np.ones((32, 32), dtype=np.float32))
    ctx["X"] = value
    entry = ctx.forms.entry("X")
    with pytest.raises(DiskBudgetError):
        ctx.forms.spill(entry, "quota")
    assert entry.form is value and entry.disk is None
    assert not list(ctx.forms.cache_root.iterdir()) and ctx.forms.disk_bytes == 0
    ctx.memory.close("failed")


def test_shared_allocation_and_pinned_emergency_spill(tmp_path):
    ctx = context(tmp_path)
    root = np.zeros((256, 256), dtype=np.float32)
    ctx["X"] = form(root)
    ctx["Y"] = form(root[:, ::2])
    # Backing payload is counted once, plus Python labels/metadata.
    assert ctx.forms.managed < ctx.forms.entry("X").size + ctx.forms.entry("Y").size
    ctx.forms.pin(["X"])
    ctx.memory.emergency_spill("test_pressure")
    ctx.forms.evict_to(0, "forced_pressure")
    assert ctx.forms.entry("X").form is not None
    assert ctx.forms.entry("Y").form is None
    with pytest.raises(ContextError):
        ctx.forms.spill(ctx.forms.entry("X"), "unsafe")
    ctx.forms.end_step()
    ctx.memory.close("failed")


@pytest.mark.parametrize("data", [np.array([[1, np.nan, np.inf], [-2, 7, 0]], dtype=np.float32),
                                   np.full((2, 3), np.nan, dtype=np.float32),
                                   np.empty((0, 3), dtype=np.float32)])
def test_stream_describe_matches_full_export(tmp_path, data):
    legacy = Context(tmp_path / "legacy", {"sources": {}, "steps": []})
    original = form(data)
    step = DescribeStep()
    step.run(legacy, [original])
    expected = step.export(legacy)
    ctx = context(tmp_path / "managed", chunk_mb=.00001)
    ctx["X"] = original
    ctx.forms.spill(ctx.forms.entry("X"), "force_disk_stream")
    run(ctx, [{"name": "describe", "inputs": ["X"]}])
    ctx.finalize()
    got = json.loads((ctx.out_dir / ctx.artifacts["exports"][0]["export_path"]).read_text())
    assert got["shape"] == expected["shape"] and got["labels"] == expected["labels"]
    for key in ("min", "max", "mean", "std", "n_valid", "n_missing"):
        a, b = got["global"][key], expected["global"][key]
        if a is None or b is None:
            assert a == b
        else:
            assert a == pytest.approx(b, rel=2e-6, abs=2e-6)
    assert ctx.memory.report["plans"][0]["mode"] == "stream"
    assert not any(e["event"] == "load" for e in events(ctx))


def test_branch_spill_reload_result_matches_legacy(tmp_path):
    data = np.arange(512 * 64, dtype=np.float32).reshape(512, 64) % 17
    steps = [{"name": "select", "inputs": ["X"], "params": {
              "dim": "feature", "labels": [f"f{i}" for i in range(32 if j == 2 else 0, 64 if j == 2 else 32)], "output": f"Q{j}"}}
             for j in range(7)]
    steps += [{"name": "pca", "inputs": ["Q0"], "params": {
               "dim": "feature", "n_components": 2, "output": "P"}},
              {"name": "concat", "inputs": ["Q1", "Q2"],
               "params": {"axis": "feature", "output": "merged"}},
              {"name": "select", "inputs": ["X"], "params": {
               "dim": "feature", "labels": ["f0", "f1"], "output": "Back"}},
              {"name": "describe", "inputs": ["Back"]}]
    old = Context(tmp_path / "old", {"sources": {}, "steps": steps})
    old["X"] = form(data.copy())
    run(old, steps)
    ctx = context(tmp_path / "new", budget=1.8)
    ctx["X"] = form(data.copy())
    run(ctx, steps)
    ctx.finalize()
    report = ctx.memory.report
    assert report["status"] == "complete"
    assert report["event_counts"].get("spill", 0) > 0
    assert report["event_counts"].get("load", 0) > 0
    assert report["managed_peak_bytes"] <= report["budget_bytes"]
    # Restore final results through the same managed store.
    np.testing.assert_allclose(ctx["P"].data, old["P"].data, atol=1e-6)
    np.testing.assert_array_equal(ctx["merged"].data, old["merged"].data)
    assert ctx["merged"].labels == old["merged"].labels


def test_alias_versions_and_complete_failure_log(tmp_path):
    ctx = context(tmp_path, budget=4)
    original = form(np.arange(16, dtype=np.float32).reshape(4, 4))
    ctx["X"] = original
    first_id = ctx.forms.entry("X").key
    steps = [{"name": "select", "inputs": ["X"], "params": {
               "dim": "feature", "labels": ["f0", "f1"], "output": "X"}},
             {"name": "unknown_step", "inputs": ["X"]}]
    with pytest.raises(Exception, match="Unknown step"):
        run(ctx, steps)
    assert ctx.forms.entry("X").key != first_id
    assert ctx["X"].data.shape == (4, 2)
    ctx.finalize()
    summary = json.loads((ctx.out_dir / "run_summary.json").read_text())
    assert summary["status"] == "failed" and summary["n_steps"] == 1
    assert Path(summary["event_log"]).exists()
    assert ctx.memory.report["error"]


def test_full_only_admission_and_live_budget_update(tmp_path):
    ctx = context(tmp_path, budget=1)
    ctx["X"] = form(np.zeros((128, 128), dtype=np.float32))
    steps = [{"name": "pca", "inputs": ["X"], "params": {"dim": "feature", "output": "P"}}]
    with pytest.raises(MemoryBudgetError):
        run(ctx, steps)
    assert "P" not in ctx.forms
    assert not ctx.forms.active
    ctx.memory.update_budget(4 * 1024**2)
    assert ctx.memory.config.budget_bytes == 4 * 1024**2
    ctx.finalize()


def test_lifetime_large_and_invalid_config():
    steps = [{"name": "describe", "inputs": ["X"]} for _ in range(100000)]
    plan = LifetimePlan(steps, STEPS)
    assert len(plan.uses["X"]) == 100000
    assert plan.next_use("X", 99998, -1) == 99999
    for raw in ({"budget_mb": -1}, {"budget_mb": True}, {"target_fraction": .9},
                {"chunk_mb": float("inf")}, {"keep": "X"}, {"profiles": {"pca": {"workspace_mb": -1}}}):
        with pytest.raises(ManifestError):
            MemoryConfig.parse({"runtime": {"memory": raw}})


def test_monitor_reads_real_rss_and_is_stopped(tmp_path):
    ctx = context(tmp_path, poll_ms=5)
    ctx.memory.configure([], STEPS)
    time.sleep(.025)
    ctx._run_status = "complete"
    ctx.finalize()
    assert ctx.memory.report["sampled_rss_peak_bytes"] > 0
    assert not ctx.memory._thread.is_alive()


def test_rss_watchdog_spills_only_unpinned_cache(tmp_path, monkeypatch):
    ctx = context(tmp_path, poll_ms=5, process_limit_mb=1000, keep=["X", "Y"])
    ctx["X"] = form(np.ones((64, 64), dtype=np.float32))
    ctx["Y"] = form(np.ones((64, 64), dtype=np.float32))
    ctx.forms.pin(["X"])
    # Controlled RSS pressure exercises the actual background thread. A
    # separate test above samples real RSS; this is failure-path injection.
    monkeypatch.setattr(ctx.memory, "_sample", lambda: 900 * 1024**2)
    ctx.memory.configure([], STEPS)
    deadline = time.monotonic() + 2
    while ctx.forms.entry("Y").form is not None and time.monotonic() < deadline:
        time.sleep(.01)
    assert ctx.forms.entry("X").form is not None
    assert ctx.forms.entry("Y").form is None and ctx.forms.entry("Y").disk
    assert any(e["event"] == "emergency_spill" and e["reason"] == "rss_pressure" for e in events(ctx))
    ctx.forms.end_step()
    ctx.memory.close("failed")


def test_replace_failure_and_managed_array_immutability(tmp_path, monkeypatch):
    ctx = context(tmp_path)
    ctx["X"] = form(np.ones((32, 32), dtype=np.float32))
    entry = ctx.forms.entry("X")
    with pytest.raises(ValueError):
        entry.form.data[0, 0] = 99
    import src.task.memory.store as store_module
    def failing_replace(*args):
        raise OSError("injected commit failure")
    monkeypatch.setattr(store_module.os, "replace", failing_replace)
    with pytest.raises(OSError, match="commit failure"):
        ctx.forms.spill(entry, "failure")
    assert entry.form is not None and entry.disk is None
    assert not list(ctx.forms.cache_root.iterdir())
    ctx.memory.close("failed")


def test_quota_full_can_evict_an_existing_disk_copy(tmp_path):
    ctx = context(tmp_path)
    ctx["X"] = form(np.ones((32, 32), dtype=np.float32))
    x = ctx.forms.entry("X")
    ctx.forms.spill(x, "make_durable_copy")
    ctx["X"]  # Reload the durable copy into RAM.
    ctx["Y"] = form(np.ones((64, 64), dtype=np.float32))
    ctx.memory.config.disk_limit_bytes = ctx.forms.disk_bytes
    unique_x = sum(size for key, size in x.refs.items() if ctx.forms.allocations[key][1] == 1)
    target = ctx.forms.managed - unique_x
    # Y is the larger, first victim but has no disk copy and cannot be written.
    # Trying X next frees enough RAM without consuming further disk space.
    ctx.forms.evict_to(target, "quota_recovery")
    assert x.form is None and x.disk is not None
    assert ctx.forms.entry("Y").form is not None
    assert ctx.forms.managed <= target
    ctx.memory.close("failed")


def test_watchdog_quota_block_is_retryable(tmp_path, monkeypatch):
    ctx = context(tmp_path, poll_ms=5, disk_limit_mb=.001, process_limit_mb=1000, keep=["Y"])
    ctx["Y"] = form(np.ones((64, 64), dtype=np.float32))
    monkeypatch.setattr(ctx.memory, "_sample", lambda: 900 * 1024**2)
    ctx.memory.configure([], STEPS)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        with ctx.memory.log_lock:
            blocked = any(e["event"] == "spill_blocked" for e in events(ctx))
        if blocked:
            break
        time.sleep(.01)
    assert blocked and ctx.memory.fault is None
    assert ctx.forms.entry("Y").form is not None
    # Available disk changes; the same running monitor must retry and recover.
    with ctx.forms.lock:
        ctx.memory.config.disk_limit_bytes = None
    deadline = time.monotonic() + 2
    while ctx.forms.entry("Y").form is not None and time.monotonic() < deadline:
        time.sleep(.01)
    assert ctx.forms.entry("Y").form is None
    ctx.memory.close("failed")


def test_rejected_budget_change_restores_previous_budget(tmp_path):
    ctx = context(tmp_path, auto_spill=False)
    ctx["X"] = form(np.ones((32, 32), dtype=np.float32))
    old_budget = ctx.memory.config.budget_bytes
    with pytest.raises(MemoryBudgetError):
        ctx.memory.update_budget(1)
    assert ctx.memory.config.budget_bytes == old_budget
    ctx.memory.close("failed")


def test_figures_are_isolated_between_managed_runs(tmp_path):
    from src.task.step.steps._plot_helpers import plt, save_figure
    paths = []
    for _ in range(2):
        ctx = context(tmp_path)
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])
        paths.append(Path(save_figure(fig, ctx, "same-name.png")))
        ctx.memory.close("failed")
    assert paths[0] != paths[1]
    assert all(p.is_file() and p.read_bytes().startswith(b"\x89PNG") for p in paths)


def test_existing_gwas_operator_graph_matches_legacy(tmp_path):
    # Exercise the upstream 16-step graph on real Forms without requiring a
    # VCF dependency. This verifies operators, not the VCF Reader.
    manifest = load_manifest(Path(__file__).resolve().parents[1] / "tasks/gwas_demo/task.yaml")
    rng = np.random.default_rng(42)
    samples, variants = 60, 30
    genotypes = rng.binomial(2, .3, (variants, samples)).astype(np.float32)
    sample_labels = {f"s{i}": i for i in range(samples)}
    genotype = Form(genotypes, ["variant", "sample"],
                    {"variant": {f"rs{i}": i for i in range(variants)}, "sample": sample_labels},
                    {"missing_code": np.nan, "ploidy": 2, "representation": "hard_call",
                     "chrom": np.ones(variants, dtype=np.int32), "pos": np.arange(variants) * 100 + 1000},
                    {"variant": ["chrom", "pos"]})
    phenotype = Form((.5 * genotypes[0] + rng.normal(size=samples)).astype(np.float32)[:, None],
                     ["sample", "feature"], {"sample": sample_labels, "feature": {"trait_value": 0}},
                     {"missing_code": np.nan})
    covariates = Form(np.column_stack([rng.integers(0, 2, samples), rng.integers(0, 3, samples)]).astype(np.float32),
                      ["sample", "feature"], {"sample": sample_labels, "feature": {"sex": 0, "batch": 1}},
                      {"missing_code": np.nan})
    contexts = []
    for mode in ("legacy", "managed"):
        config = {"sources": {}, "steps": manifest["steps"]}
        if mode == "managed":
            config["runtime"] = {"memory": {"budget_mb": 64,
                                           "keep": ["pcs", "assoc_result", "assoc_with_pos"]}}
        ctx = Context(tmp_path / mode, config)
        for name, value in (("geno", genotype), ("pheno", phenotype), ("covar", covariates)):
            ctx[name] = value
        run(ctx, manifest["steps"])
        ctx.finalize()
        contexts.append(ctx)
    old, new = contexts
    for name in ("pcs", "assoc_result", "assoc_with_pos"):
        np.testing.assert_allclose(new[name].data, old[name].data, rtol=1e-6, atol=1e-6, equal_nan=True)
        assert new[name].labels == old[name].labels
        assert new[name].axis_info == old[name].axis_info
    assert new["assoc_with_pos"].info["pos"] == old["assoc_with_pos"].info["pos"]
    assert len(new.artifacts["exports"]) == 16
    figures = list(new.memory.run_dir.glob("figures/*.png"))
    assert len(figures) == 3 and all(p.stat().st_size > 100 for p in figures)


def test_attach_info_does_not_mutate_cached_input_encoders(tmp_path):
    ctx = context(tmp_path, keep=["target"])
    encoder = get_encoder("labelencoder")
    encoder.fit_transform(["a", "b"])
    ctx["target"] = form(np.ones((1, 2), dtype=np.float32),
                         {"missing_code": np.nan, "encoders": {"feature": {"f0": encoder}}})
    source = form(np.ones((1, 2), dtype=np.float32), {"chrom": ["chr1", "chr2"]})
    source.axis_info = {"feature": ["chrom"]}
    ctx["source"] = source
    ctx.forms.spill(ctx.forms.entry("target"), "preexisting_cache")
    steps = [{"name": "attach_info", "inputs": ["target", "source"],
              "params": {"fields": ["chrom"], "target_dim": "feature", "output": "annotated"}},
             {"name": "describe", "inputs": ["target"]}]
    try:
        run(ctx, steps)
        assert "chrom" not in ctx["target"].info["encoders"]["feature"]
        assert "chrom" in ctx["annotated"].info["encoders"]["feature"]
    finally:
        ctx.finalize()
    assert "chrom" not in ctx["target"].info["encoders"]["feature"]
