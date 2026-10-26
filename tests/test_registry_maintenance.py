from extension_fixtures import write_extension
"""Maintenance discovers filesystem additions and publishes only valid indexes."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from biopipe.packages import bundled_state
from biopipe.plugins import PluginManager, active_descriptors

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    for name in ("src", "biopipe", "biopipe_sdk", "routes", "scripts"):
        shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


def cli(root, *args):
    process = subprocess.run([sys.executable, "-m", "biopipe", "registry", *args], cwd=root,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert process.stdout, process.stderr
    return process.returncode, json.loads(process.stdout)


NEW_OPERATOR = '''from biopipe_sdk import Step, port
class Probe(Step):
    name = "example.probe"
    category = "analysis"
    icon = "Sigma"
    inputs_arity = 1
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    input_contracts = [port(ndim=2)]
    output_contract = {"mode": "report"}
    def run(self, ctx, inputs):
        pass
'''


def add_extension(root, source=NEW_OPERATOR):
    path = root / "src/task/step/steps/example_probe.py"
    write_extension(path, source)
    return path


def indexes(root):
    return [(root / path).read_bytes() for path in ("biopipe/builtin_packages.json", "src/web/builtin_routes.json")]


def test_discover_build_check_new_operator_and_unlisted_route(checkout):
    add_extension(checkout)
    path = checkout / "routes/custom/nested/task.yml"
    path.parent.mkdir(parents=True)
    path.write_text('''name: Custom report
sources:
  counts:
    path: input/counts.csv
    dims: [sample, feature]
steps:
  - name: example.probe
    inputs: [counts]
''', encoding="utf-8")
    code, discovery = cli(checkout, "discover")
    assert code == 0
    assert any(d["id"] == "example.probe" and not d["indexed"] for d in discovery["extensions"])
    assert any(r["name"] == "Custom report" for r in discovery["routes"])
    before = indexes(checkout)
    code, check = cli(checkout, "check")
    assert code == 1 and check["changed"] and not check["errors"] and indexes(checkout) == before
    code, built = cli(checkout, "build")
    operator_count = sum(d["kind"] == "operator" for d in bundled_state()["descriptors"])
    assert code == 0 and built["operators"] == operator_count + 1 and built["routes"] == 6
    manifest = json.loads((checkout / "biopipe/builtin_packages.json").read_text(encoding="utf-8"))
    descriptor = next(d for p in manifest["packages"] for d in p["descriptors"] if d["id"] == "example.probe")
    assert descriptor["category"] == "analysis" and descriptor["icon"] == "Sigma"
    code, check = cli(checkout, "check")
    assert code == 0 and not check["changed"]
    assert next(r for r in cli(checkout, "discover")[1]["routes"] if r["name"] == "Custom report")["indexed"]
    after = indexes(checkout)
    assert cli(checkout, "build")[1]["written"] == [] and indexes(checkout) == after


def test_sdk_operator_is_discovered_and_missing_startup_index_can_be_rebuilt(checkout):
    add_extension(checkout, NEW_OPERATOR.replace('Step, port', 'Operator, port').replace('class Probe(Step)', 'class Probe(Operator)')
                  .replace('    def run(self, ctx, inputs):', '    output_parameter = None\n    def compute(self, inputs, params, context):'))
    code, result = cli(checkout, "discover")
    assert code == 0 and any(e['id'] == 'example.probe' and e['kind'] == 'operator' for e in result['extensions'])
    index = checkout / 'biopipe/builtin_packages.json'
    value = json.loads(index.read_text(encoding='utf-8'))
    # A removed module referenced by an old startup index must not block repair.
    entry = deepcopy(next(d for p in value['packages'] for d in p['descriptors'] if d['id'] == 'diversity'))
    entry.update(id='removed.operator', entry_point='src.task.step.steps.deleted:Deleted')
    value['packages'][0]['descriptors'].append(entry)
    index.write_text(json.dumps(value), encoding='utf-8')
    code, report = cli(checkout, 'build')
    assert code == 0 and not report['errors']
    assert 'removed.operator' not in index.read_text(encoding='utf-8')
    runtime = subprocess.run([sys.executable, '-c', "from src.task import STEPS; assert not hasattr(STEPS['example.probe'], 'legacy_parameters')"],
                             cwd=checkout, capture_output=True, text=True, timeout=30)
    assert runtime.returncode == 0, runtime.stderr


@pytest.mark.parametrize("source,expected", [
    (NEW_OPERATOR.replace('parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}', 'parameters_schema = None'), "parameters_schema"),
    (NEW_OPERATOR.replace('name = "example.probe"', 'name = "diversity"'), "Duplicate"),
    (NEW_OPERATOR.replace('output_contract = {"mode": "report"}', 'output_contract = {"mode": "invented"}'), "contract mode"),
])
def test_invalid_extension_does_not_publish_partial_indexes(checkout, source, expected):
    add_extension(checkout, source)
    before = indexes(checkout)
    code, report = cli(checkout, "build")
    assert code == 1 and report["written"] == []
    assert any(expected in error["error"] for error in report["errors"])
    assert indexes(checkout) == before


def test_missing_route_operator_does_not_publish_and_custom_root_works(checkout):
    custom = checkout / "extra_routes/new"
    custom.mkdir(parents=True)
    source = (checkout / "routes/microbiome/task.yaml").read_text(encoding="utf-8")
    (custom / "task.yaml").write_text(source.replace("name: diversity", "name: missing.operator"), encoding="utf-8")
    before = indexes(checkout)
    code, report = cli(checkout, "build", "--route-root", "extra_routes")
    assert code == 1 and any("missing.operator" in e["error"] for e in report["errors"])
    assert indexes(checkout) == before
    (custom / "task.yaml").write_text(source, encoding="utf-8")
    code, report = cli(checkout, "build", "--route-root", "extra_routes", "--output-dir", str(checkout / "generated"))
    assert code == 0 and report["routes"] == 1 and indexes(checkout) == before


def test_new_bundled_package_migrates_without_restoring_removals(tmp_path):
    manager = PluginManager(tmp_path)
    manager.directory.mkdir(parents=True)
    state = deepcopy(bundled_state())
    state["packages"] = [p for p in state["packages"] if p["name"] != "biopipe-microbiome"]
    state["descriptors"] = [d for d in state["descriptors"] if d["distribution"] != "biopipe-microbiome"]
    state.update(protocol_version=3, package_protocol_version=3, generation="before16s", bundled_seen=[p["name"] for p in state["packages"]])
    history = manager.directory / "snapshots"
    history.mkdir()
    (history / "old.json").write_text(json.dumps(state), encoding="utf-8")
    state["packages"] = [p for p in state["packages"] if p["name"] != "biopipe-genetics"]
    state["descriptors"] = [d for d in state["descriptors"] if d["distribution"] != "biopipe-genetics"]
    next(p for p in state["packages"] if p["name"] == "biopipe-core")["enabled"] = False
    manager.registry.write_text(json.dumps(state), encoding="utf-8")
    updated = manager.state()
    names = {p["name"] for p in updated["packages"]}
    assert "biopipe-microbiome" in names and "biopipe-genetics" not in names
    assert not next(p for p in updated["packages"] if p["name"] == "biopipe-core")["enabled"]
    assert "diversity" in {d["id"] for d in active_descriptors(updated)}
    assert manager.state()["generation"] == updated["generation"]
    manager.manage("biopipe-microbiome", "remove")
    assert "biopipe-microbiome" not in {p["name"] for p in manager.state()["packages"]}
    manager.manage("biopipe-microbiome", "restore")
    assert "diversity" in {d["id"] for d in active_descriptors(manager.state())}


def test_maintenance_never_executes_module_top_level(checkout):
    add_extension(checkout, NEW_OPERATOR + '\nraise RuntimeError("must not execute")\n')
    code, report = cli(checkout, "build")
    assert code == 0 and report["errors"] == []
    assert report["operators"] == 65
