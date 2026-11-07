from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = ROOT / "examples" / "route_combinations"
CASES = [
    "refseq_cds_sequence_features",
    "thousand_genomes_chr22_population",
    "leukemia_all_aml_expression",
    "pbmc3k_single_cell_atlas",
    "qiime_moving_pictures_microbiome",
]
THRESHOLDS = {
    "refseq_cds_sequence_features": 11,
    "thousand_genomes_chr22_population": 13,
    "leukemia_all_aml_expression": 11,
    "pbmc3k_single_cell_atlas": 12,
    "qiime_moving_pictures_microbiome": 13,
}


def _run(task_dir: Path, *extra: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'MPLBACKEND': 'Agg'}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run.py"), str(task_dir), *extra],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        env=environment,
        timeout=timeout,
    )


def test_route_examples_are_curated_five() -> None:
    dirs = sorted(path.name for path in EXAMPLE_ROOT.iterdir() if path.is_dir())
    assert dirs == sorted(CASES)
    for name in CASES:
        assert (EXAMPLE_ROOT / name / "ANALYSIS.md").is_file(), f"{name} lacks ANALYSIS.md"
        import yaml
        topology = yaml.safe_load((EXAMPLE_ROOT / name / 'task.yaml').read_text(encoding='utf-8'))
        assert topology['parameters_file'] == 'parameters.json'
        assert all('params' not in step for step in topology['steps'])
        assert all(source.get('reader') and 'args' not in source for source in topology['sources'].values())


@pytest.mark.parametrize("name", CASES)
def test_route_combination_check(name: str) -> None:
    proc = _run(EXAMPLE_ROOT / name, "--check", timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CHECK OK" in proc.stdout


@pytest.mark.parametrize("name", CASES)
def test_route_combination_executes_in_tmp(name: str, tmp_path: Path) -> None:
    dst = tmp_path / name
    shutil.copytree(
        EXAMPLE_ROOT / name,
        dst,
        ignore=shutil.ignore_patterns("output"),
    )
    proc = _run(dst, '--memory-mb', '512')
    (dst / 'validation-process.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary_path = dst / "output" / "run_summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    assert summary["n_steps"] >= THRESHOLDS[name]
    assert Path(summary['memory_report']).is_file()
    figures = list((Path(summary['memory_report']).parent / 'figures').glob('*.png'))
    assert figures, 'The example must produce actual figures'
    for path in figures:
        assert path.with_suffix('.pdf').is_file()
        assert path.with_suffix('.svg').is_file()


@pytest.mark.parametrize('task_path', sorted((ROOT / 'routes').glob('*/task.yaml')), ids=lambda path: path.parent.name)
def test_route_template_contracts_and_parameter_snapshots(task_path: Path) -> None:
    import yaml
    from operon.packages import bundled_state
    from src.task.manifest import load_manifest
    from src.web.graph import compile_graph, import_manifest
    from src.web.operator_catalog import catalog_from_descriptors

    value = load_manifest(task_path)
    catalog = catalog_from_descriptors(bundled_state()['descriptors'])
    graph = import_manifest(yaml.safe_dump(value), '.', catalog, task_path.parent)
    compiled, _ = compile_graph(graph, catalog, task_path.parent, require_files=False)
    assert len(compiled['steps']) == len(value['steps'])
    topology = yaml.safe_load(task_path.read_text(encoding='utf-8'))
    if topology.get('parameters_file'):
        assert all('params' not in step for step in topology['steps'])
        assert (task_path.parent / topology['parameters_file']).is_file()
