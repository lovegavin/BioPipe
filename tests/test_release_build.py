"""Release archives must preserve the v3 authoring and runtime contract."""
import json
from pathlib import Path
import sys
import zipfile

from scripts.build_runtime import windows_descriptors, runtime_requirements


def test_management_runtime_does_not_expand_with_operator_library():
    project = {'dependencies': ['numpy>=1.26', 'fastapi>=0.115'],
               'optional-dependencies': {'agent': ['mcp>=1.20,<2']}}
    manifest = {'packages': [{'descriptors': [{'id': 'large', 'dependencies': ['torch>=2', 'pandas>=2']}]}]}
    requirements, selected = runtime_requirements(project, manifest)
    assert selected == []
    assert 'torch>=2' not in requirements and 'pandas>=2' not in requirements
    assert 'mcp>=1.20,<2' in requirements and 'numpy>=1.26' in requirements
    full, selected = runtime_requirements(project, manifest, 'analysis')
    assert 'torch>=2' in full and selected[0]['id'] == 'large'


def test_seed_declares_analysis_requirements_previously_supplied_by_full_runtime():
    root = Path(__file__).resolve().parents[1]
    index = json.loads((root / 'library/seed/biopipe/builtin_packages.json').read_text(encoding='utf-8'))
    descriptors = {d['id']: d for p in index['packages'] for d in p['descriptors']}
    assert 'pandas>=2.0' in descriptors['CsvReader']['dependencies']
    assert 'matplotlib>=3.8' in descriptors['scatter']['dependencies']
    assert 'pandas' in descriptors['CsvReader']['dependency_imports']
    assert 'matplotlib' in descriptors['scatter']['dependency_imports']
    assert not descriptors['pca'].get('dependencies')


def test_windows_runtime_keeps_portable_dependencies_and_excludes_unix_only_tools():
    items = [
        {"id": "table", "dependencies": ["openpyxl>=3.1"]},
        {"id": "bam", "dependencies": ["pysam>=0.22"]},
        {"id": "signal", "dependencies": ["pyBigWig"]},
        {"id": "align", "resources": {"external_tools": ["bwa"]}},
        {"id": "conditional", "dependencies": ['pysam; sys_platform == "linux"']},
        {"id": "dedicated", "dependencies": ['numpy==1.26.4'], "resources": {"environment": "example"}},
        {"id": "vina_python", "dependencies": ['vina>=1.2']},
    ]
    manifest = {"packages": [{"descriptors": items}]}
    assert [d["id"] for d in windows_descriptors(manifest)] == ["table", "conditional"]


def test_lite_archive_preserves_operator_docs_and_frozen_task_parameters(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from scripts import package_release

    root = tmp_path / "source"
    files = {
        "pyproject.toml": '[project]\nversion="0.0.1"\n',
        "README.md": "Example release",
        "src/example.py": "# Example operator",
        "src/example.parameters.json": '{"default": 20}',
        "src/example.Operator.md": "# Operator usage",
        "tasks/example/task.yaml": "name: example",
        "tasks/example/parameters.json": '{"value": 10}',
        "tasks/example/output/unrelated.json": '{"private": true}',
        "scripts/desktop_server.py": "# Desktop entry",
        "scripts/install_maintenance.py": "# Setup runtime inspection",
        "scripts/install_server.py": "# Server CLI installation",
        "scripts/install_server.sh": "# Linux Python bootstrap",
        "scripts/run.py": "# Worker entry",
        "scripts/diagnose_pins.py": "# Diagnostic entry",
        "scripts/check_resources.py": "# Resource inspection",
        "scripts/provision_resources.py": "# Resource provisioning",
        "scripts/accept_igv_handoff.py": "# IGV acceptance",
        "scripts/open_igv_handoff.ps1": "# IGV launcher",
        "scripts/verify_release_agent.py": "# Agent acceptance",
        "scripts/verify_operon_candidate.py": "# Operon packaged runtime acceptance",
        "scripts/verify_server_cli.py": "# Real terminal acceptance",
        "scripts/verify_release_agent.md": "# Agent acceptance guide",
        "frontend/dist/index.html": "<title>Studio</title>",
        "frontend/package-lock.json": '{"packages": {}}',
        "docs/example.md": "Example documentation",
        "examples/extension/example.md": "Example extension",
        "THIRD_PARTY_NOTICES/example.txt": "Example license",
        "host/Operon Studio.exe": "EXE placeholder for packaging-only regression",
    }
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    monkeypatch.setattr(package_release, "__file__", str(root / "scripts/package_release.py"))
    monkeypatch.setattr(package_release.subprocess, "check_output", lambda *a, **k: "a" * 40)
    monkeypatch.setattr(sys, "argv", ["package_release.py", "--lite", "--desktop", str(root / "host"),
                                     "--output", str(tmp_path / "archives")])
    package_release.main()
    with zipfile.ZipFile(next((tmp_path / "archives").glob("*.zip"))) as archive:
        prefix = "Operon Studio/"
        assert archive.read(prefix + "src/example.Operator.md").decode() == "# Operator usage"
        assert json.loads(archive.read(prefix + "src/example.parameters.json"))["default"] == 20
        assert json.loads(archive.read(prefix + "tasks/example/parameters.json"))["value"] == 10
        assert prefix + "tasks/example/output/unrelated.json" not in archive.namelist()
        manifest = json.loads(archive.read(prefix + "package-manifest.json"))
        assert "src/example.Operator.md" in {row["path"] for row in manifest["files"]}
        assert manifest["product"] == "operon"
        assert "operon.cmd" in {row["path"] for row in manifest["files"]}
        assert "scripts/install_server.sh" in {row["path"] for row in manifest["files"]}
        assert "Registration and startup read metadata" in archive.read(prefix + "START_HERE.txt").decode()
