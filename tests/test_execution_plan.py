"""Placement contracts without SSH, scientific imports, or data payload reads."""
from copy import deepcopy

import pytest

from src.web import execution_plan as planner
from src.web.graph import GraphError
from src.web.models import Graph


LOCAL = {"kind": "local"}
SSH = {"kind": "ssh", "profile_id": "compute"}


def source(name="input", location=None, path="counts.csv", args=None):
    return {"id": name, "kind": "source", "title": name,
            "position": {"x": 0, "y": 0}, "input_count": 0,
            "source": {"path": path, 'args': args or {}, **({"location": location} if location else {})}}


def operator(name, op="portable", **extra):
    return {"id": name, "kind": "operator", "operator": op, "title": name,
            "position": {"x": 0, "y": 0}, **extra}


def graph(nodes, edges=(), **execution):
    return Graph.model_validate({"nodes": nodes,
        "edges": [{"id": f"e{i}", "source": left, "target": right}
                  for i, (left, right) in enumerate(edges)],
        "runtime": {"execution": execution}})


def spec(name="portable", systems=None, tools=(), parameters=None, **extra):
    return {"id": name, "supported_systems": systems or ["windows", "linux"],
            "resources": {"external_tools": list(tools)},
            'parameters_schema': {'properties': parameters or {}}, **extra}


def reader(systems=None, **extra):
    return spec('CsvReader', systems, extensions=['.csv'], **extra)


def host(target=LOCAL, system="windows", specs=None, tools=None, readers=None, **extras):
    return {"target": deepcopy(target), "name": planner.target_key(target), "system": system,
            "catalog": {"operators": specs if specs is not None else [spec()],
                        'readers': readers if readers is not None else [reader()]},
            "tools": tools or {}, "resources": {"active_jobs": 0, "queued_jobs": 0}, **extras}


def targets(plan):
    return {key: unit["target"] for unit in plan["units"] for key in unit["node_ids"]}


def test_manual_target_overrides_and_legacy_default_are_preserved():
    workflow = graph([source(location=LOCAL), operator("local"), operator("remote"), operator("finish")],
                     [("input", "local"), ("local", "remote"), ("remote", "finish")],
                     kind="local", node_targets={"remote": SSH})
    original = workflow.model_dump()
    plan = planner.make_plan(workflow, [host(), host(SSH, "linux")], stat_file=lambda *_: 100)
    assert plan["mode"] == "manual"
    assert targets(plan) == {"local": LOCAL, "remote": SSH, "finish": LOCAL}
    assert [unit["depends_on"] for unit in plan["units"]] == [[], ["stage_1"], ["stage_2"]]
    assert [(item["source"], item["target"]) for item in plan["transfers"]] == [("local", "remote"), ("remote", "finish")]
    assert workflow.model_dump() == original
    old = graph([source(), operator("step")], [("input", "step")], kind="ssh", profile_id="compute")
    assert planner.make_plan(old, [host(SSH, "linux")])["transfers"] == []


def test_local_data_uploads_when_entire_manual_workflow_selects_ssh():
    workflow = graph([source(location=LOCAL), operator("step")], [("input", "step")],
                     kind="ssh", profile_id="compute", mode="manual")
    plan = planner.make_plan(workflow, [host(), host(SSH, "linux")], stat_file=lambda *_: 1024)
    assert targets(plan) == {"step": SSH}
    assert plan["transfers"] == [{"source": "input", "target": "step", "from": LOCAL, "to": SSH, "estimated_bytes": 1024}]


def test_linux_requirement_moves_automatic_operator_and_rejects_manual_windows():
    specs = [spec("hic", ["linux"])]
    infos = [host(specs=specs), host(SSH, "linux", specs)]
    workflow = graph([source(location=LOCAL), operator("hic", "hic")], [("input", "hic")], mode="auto")
    assert targets(planner.make_plan(workflow, infos)) == {"hic": SSH}
    workflow.runtime["execution"]["mode"] = "manual"
    with pytest.raises(GraphError, match="selected environment is unavailable.*requires linux") as error:
        planner.make_plan(workflow, infos)
    assert error.value.node_id == "hic"


def test_missing_executable_and_failed_python_dependencies_exclude_hosts():
    specs = [spec("align", ["linux"], ["bwa", "samtools"])]
    workflow = graph([operator("align", "align")], mode="auto")
    missing = host(SSH, "linux", specs, {"bwa": True, "samtools": False})
    with pytest.raises(GraphError, match="Missing executable: samtools"):
        planner.make_plan(workflow, [missing])
    missing["tools"]["samtools"] = True
    missing["dependencies"] = {"entries": [{"id": "align", "status": "failed"}]}
    with pytest.raises(GraphError, match="dependencies are not ready"):
        planner.make_plan(workflow, [missing])
    missing["dependencies"]["entries"][0]["status"] = "passed"
    assert targets(planner.make_plan(workflow, [missing])) == {"align": SSH}


def test_absent_operator_is_not_silently_replaced():
    workflow = graph([operator("custom", "not_installed")], mode="auto")
    with pytest.raises(GraphError, match="not_installed is not installed"):
        planner.make_plan(workflow, [host()])


def test_explicit_manual_target_cannot_fall_back_to_a_healthy_machine():
    workflow = graph([operator("step")], mode="manual", node_targets={"step": SSH})
    with pytest.raises(GraphError, match="selected environment is unavailable"):
        planner.make_plan(workflow, [host()])
    workflow.runtime["execution"] = {"kind": "ssh", "profile_id": "offline"}
    with pytest.raises(GraphError, match="selected environment is unavailable"):
        planner.make_plan(workflow, [host(), host(SSH, "linux")])


def test_nested_route_is_an_atomic_placement_unit():
    inner = graph([operator("portable"), operator("hic", "hic")], [("portable", "hic")],
                  mode="manual", node_targets={"hic": LOCAL})
    route = {"id": "route", "kind": "route", "position": {"x": 0, "y": 0},
             "route": {"id": "route_123456abcdef", "version": 1, "name": "Hi-C", "graph": inner.model_dump()}}
    workflow = graph([source(location=LOCAL), route], [("input", "route")], mode="auto")
    specs = [spec(), spec("hic", ["linux"])]
    before = workflow.model_dump()
    plan = planner.make_plan(workflow, [host(specs=specs), host(SSH, "linux", specs)])
    assert targets(plan) == {"route": SSH}
    assert len(plan["units"]) == 1
    assert plan["units"][0]["node_ids"] == ["route"]
    assert workflow.model_dump() == before


def test_route_rejects_environment_missing_one_internal_operator():
    route = {"id": "route", "kind": "route", "position": {"x": 0, "y": 0},
             "route": {"id": "route_123456abcdef", "version": 1, "name": "Route",
                       "graph": graph([operator("custom", "not_installed")]).model_dump()}}
    with pytest.raises(GraphError, match="not_installed is not installed"):
        planner.make_plan(graph([route]), [host()])


def test_auto_prioritizes_large_input_locality_over_default_preference():
    workflow = graph([source("small", LOCAL), source("large", SSH), operator("merge")],
                     [("small", "merge"), ("large", "merge")], mode="auto", kind="local")
    calls = []
    def stat(location, path, base):
        calls.append((deepcopy(location), path, base))
        return 1024**3 if location == SSH else 1024
    plan = planner.make_plan(workflow, [host(), host(SSH, "linux")], stat_file=stat)
    assert targets(plan) == {"merge": SSH}
    assert len(calls) == 2
    assert len(plan["transfers"]) == 1
    assert plan["transfers"][0]["source"] == "small"
    assert plan["transfers"][0]["estimated_bytes"] == 1024


def test_auto_does_not_make_portable_preprocessing_bounce_between_machines():
    specs = [spec(), spec("hic", ["linux"])]
    workflow = graph([source(location=SSH), operator("prepare"), operator("hic", "hic"), operator("report")],
                     [("input", "prepare"), ("prepare", "hic"), ("hic", "report")], mode="auto", kind="local")
    plan = planner.make_plan(workflow, [host(specs=specs), host(SSH, "linux", specs)], stat_file=lambda *_: 1024**3)
    assert set(map(planner.target_key, targets(plan).values())) == {"compute"}
    assert len(plan["units"]) == 1
    assert not plan["transfers"]


def test_auto_uses_queue_pressure_and_restricts_eligible_targets():
    workflow = graph([operator("step")], mode="auto", kind="local")
    crowded = host(resources={"queued_jobs": 5, "active_jobs": 2})
    infos = [crowded, host(SSH, "linux")]
    assert targets(planner.make_plan(workflow, infos)) == {"step": SSH}
    workflow.runtime["execution"]["eligible_targets"] = [LOCAL]
    assert targets(planner.make_plan(workflow, infos)) == {"step": LOCAL}


def test_unknown_sizes_are_explicit_and_stat_failure_becomes_warning():
    workflow = graph([source(location=LOCAL), operator("step")], [("input", "step")],
                     kind="ssh", profile_id="compute")
    def unavailable(*_):
        raise OSError("metadata unavailable")
    plan = planner.make_plan(workflow, [host(), host(SSH, "linux")], stat_file=unavailable)
    assert plan["transfers"][0]["estimated_bytes"] is None
    assert len(plan["warnings"]) == 1
    assert "metadata unavailable" in plan["warnings"][0]


@pytest.mark.parametrize("config,match", [
    ({"mode": "magic"}, "mode"),
    ({"kind": "docker"}, "Invalid execution environment"),
    ({"kind": "ssh"}, "Choose a server"),
    ({"node_targets": []}, "node_targets must be an object"),
    ({"file_locations": []}, "file_locations must be an object"),
    ({"node_targets": {"missing": LOCAL}}, "missing nodes"),
    ({"max_parallel_tasks": 0}, "positive integer"),
    ({"max_parallel_tasks": 1.5}, "positive integer"),
    ({"max_parallel_tasks": True}, "positive integer"),
])
def test_invalid_execution_configuration_is_rejected(config, match):
    with pytest.raises(GraphError, match=match):
        planner.make_plan(graph([operator("step")], **config), [host()])


@pytest.mark.parametrize("nodes,edges,match", [
    ([operator("a"), operator("b")], [("a", "b"), ("b", "a")], "cycle"),
    ([operator("a")], [("missing", "a")], "missing node"),
    ([operator("same"), operator("same")], [], "Duplicate node ID"),
    ([operator("a"), source()], [("a", "input")], "Input nodes cannot have incoming"),
    ([source()], [], "at least one analysis operator"),
])
def test_invalid_dag_is_rejected(nodes, edges, match):
    with pytest.raises(GraphError, match=match):
        planner.make_plan(graph(nodes, edges), [host()])


def test_branching_stages_form_a_dependency_dag_and_keep_every_cross_stage_edge():
    nodes = [source(location=LOCAL), operator("a"), operator("b"), operator("c"), operator("d"), operator("join")]
    edges = [("input", "a"), ("a", "b"), ("a", "c"), ("b", "d"), ("c", "join"), ("d", "join")]
    workflow = graph(nodes, edges, mode="manual", node_targets={"b": SSH, "d": SSH})
    plan = planner.make_plan(workflow, [host(), host(SSH, "linux")])
    owner = {node: unit["id"] for unit in plan["units"] for node in unit["node_ids"]}
    seen = set()
    dependencies = {}
    for unit in plan["units"]:
        dependencies[unit["id"]] = set(unit["depends_on"])
        assert dependencies[unit["id"]] <= seen
        seen.add(unit["id"])
    for left, right in edges:
        if left in owner and owner[left] != owner[right]:
            assert owner[left] in dependencies[owner[right]]
    assert len(owner) == 5


def test_large_graph_has_bounded_capability_work_without_assignment_enumeration(monkeypatch):
    count, hosts = 850, 4
    workflow = graph([source(location=LOCAL)] + [operator(f"n{i}") for i in range(count)],
        [("input", "n0")] + [(f"n{i-1}", f"n{i}") for i in range(1, count)], mode="auto")
    infos = [host()] + [host({"kind": "ssh", "profile_id": f"server{i}"}, "linux") for i in range(hosts - 1)]
    original = planner.capability
    calls = 0
    def counted(*args):
        nonlocal calls
        calls += 1
        return original(*args)
    monkeypatch.setattr(planner, "capability", counted)
    plan = planner.make_plan(workflow, infos, stat_file=lambda *_: 1024**3)
    assert calls == count * hosts
    assert len(targets(plan)) == count
    assert plan["algorithm"] == "bounded-locality-v1"
    assert plan["optimality"] == "heuristic"
    assert len(plan["units"]) == 1


@pytest.mark.parametrize("eligible", [None, False, {}])
def test_eligible_target_list_has_a_typed_validation_error(eligible):
    with pytest.raises(GraphError, match="eligible_targets"):
        planner.make_plan(graph([operator("step")], mode="auto", eligible_targets=eligible), [host()])


def test_disconnected_explicit_source_location_is_not_a_valid_transfer_origin():
    workflow = graph([source(location=SSH), operator("step")], [("input", "step")], mode="auto")
    with pytest.raises(GraphError, match="(?:source|input|environment|server|connected|available)"):
        planner.make_plan(workflow, [host()])


def test_large_remote_reference_places_small_local_reads_on_server():
    specs = [spec(parameters={'reference': {'x-biopipe-path': 'workflow'}})]
    workflow = graph([source(location=LOCAL), operator('align', params={'reference': '/refs/genome.fa'})],
                     [('input', 'align')], mode='auto', file_locations={'align.params.reference': SSH})
    calls = []
    def stat(location, path, base):
        calls.append((location, path, base))
        return 8 * 1024**3 if path.endswith('.fa') else 1024
    infos = [host(specs=specs), host(SSH, 'linux', specs)]
    plan = planner.make_plan(workflow, infos, stat_file=stat)
    assert targets(plan) == {'align': SSH}
    assert len(calls) == 2  # No repeated stat during the four sweeps.
    assert plan['transfers'][0]['source'] == 'input'
    workflow.runtime['execution']['mode'] = 'manual'
    plan = planner.make_plan(workflow, infos, stat_file=stat)
    transfer = next(item for item in plan['transfers'] if item.get('parameter'))
    assert transfer == {'source': 'align', 'target': 'align', 'from': SSH, 'to': LOCAL,
                        'parameter': 'align.params.reference', 'path': '/refs/genome.fa', 'base_dir': '.',
                        'estimated_bytes': 8 * 1024**3}


def test_source_argument_reference_base_and_cost_follow_explicit_location():
    readers = [reader(parameters={'index': {'x-biopipe-path': 'source'}})]
    workflow = graph([source(location=LOCAL, path='reads/counts.csv', args={'index': 'large.idx'}), operator('step')],
                     [('input', 'step')], mode='auto', file_locations={'input.source.args.index': SSH})
    workflow.base_dir = 'project'
    calls = []
    def stat(where, path, base):
        calls.append((where, path, base))
        return 4 * 1024**3 if path.endswith('.idx') else 100
    infos = [host(readers=readers), host(SSH, 'linux', readers=readers)]
    assert targets(planner.make_plan(workflow, infos, stat_file=stat)) == {'step': SSH}
    assert (SSH, 'large.idx', 'project') in calls
    workflow.runtime['execution']['file_locations'] = {}
    calls.clear()
    planner.make_plan(workflow, infos, stat_file=stat)
    assert any(where == LOCAL and path == 'large.idx' and base.replace('\\', '/') == 'project/reads'
               for where, path, base in calls)


def test_route_internal_reference_is_costed_once_for_the_atomic_route():
    specs = [spec(parameters={'reference': {'x-biopipe-path': 'workflow'}})]
    inner = graph([source('placeholder', path='never-stat.csv'), operator('align', params={'reference': 'genome.fa'})],
                  [('placeholder', 'align')], mode='manual', file_locations={'align.params.reference': SSH})
    inner.base_dir = 'references'
    route = {'id': 'route', 'kind': 'route', 'position': {'x': 0, 'y': 0},
             'route': {'id': 'route_123456abcdef', 'version': 1, 'name': 'Route', 'graph': inner.model_dump()}}
    workflow = graph([source(location=LOCAL), route], [('input', 'route')], mode='auto')
    calls = []
    def stat(where, path, base):
        calls.append((where, path, base))
        return 9 * 1024**3 if path.endswith('.fa') else 100
    infos = [host(specs=specs), host(SSH, 'linux', specs)]
    assert targets(planner.make_plan(workflow, infos, stat_file=stat)) == {'route': SSH}
    assert calls == [(LOCAL, 'counts.csv', '.'), (SSH, 'genome.fa', 'references')]
    workflow.runtime['execution']['mode'] = 'manual'
    transfer = next(t for t in planner.make_plan(workflow, infos, stat_file=stat)['transfers'] if t.get('parameter'))
    assert transfer['source'] == transfer['target'] == 'route'
    assert transfer['parameter'] == 'route.align.params.reference'


@pytest.mark.parametrize('locations', [
    {'missing.params.reference': LOCAL}, {'step.params.output': LOCAL},
    {'step.params.reference': None}, {'step.params.reference': []},
    {'step.params.reference': {'kind': 'ssh', 'profile_id': 'offline'}},
    {'input.source.path': LOCAL},
])
def test_invalid_file_location_references_fail_before_any_execution(locations):
    specs = [spec(parameters={'reference': {'x-biopipe-path': 'workflow'}})]
    workflow = graph([source(), operator('step', params={'reference': 'reference.fa'})],
                     [('input', 'step')], mode='auto', file_locations=locations)
    with pytest.raises(GraphError, match='file_locations|Reference environment'):
        planner.make_plan(workflow, [host(specs=specs)])


def test_reader_platform_and_dependency_apply_only_where_raw_source_is_read():
    workflow = graph([source(location=SSH), operator('read'), operator('downstream', 'linux_only')],
                     [('input', 'read'), ('read', 'downstream')], mode='auto')
    specs = [spec(), spec('linux_only', ['linux'])]
    infos = [host(specs=specs, readers=[reader(['windows'])]),
             host(SSH, 'linux', specs, readers=[reader(['windows'])])]
    assert targets(planner.make_plan(workflow, infos)) == {'read': LOCAL, 'downstream': SSH}
    infos[0]['dependencies'] = {'entries': [{'id': 'CsvReader', 'status': 'failed'}]}
    with pytest.raises(GraphError, match='CsvReader dependencies are not ready'):
        planner.make_plan(workflow, infos)


def implementation(package='custom-wheel', version='1.0', sha='artifact', code='code'):
    return {'package': package, 'version': version, 'sha256': sha, 'code_sha': code, 'declaration_sha': 'metadata'}


@pytest.mark.parametrize('change', [{'sha256': 'changed'}, {'version': '2.0'}, {'package': 'other'}, {'code_sha': 'changed'}])
def test_auto_rejects_third_party_implementation_substitution(change):
    pin = implementation()
    workflow = graph([operator('step')], mode='auto')
    workflow.plugin_lock = {'portable': pin}
    exact = spec(origin='wheel', implementation=pin)
    changed = spec(origin='wheel', implementation={**pin, **change})
    infos = [host(specs=[changed]), host(SSH, 'linux', [exact])]
    assert targets(planner.make_plan(workflow, infos)) == {'step': SSH}
    with pytest.raises(GraphError, match='pinned implementation'):
        planner.make_plan(workflow, infos[:1])


def test_bundled_default_changes_and_known_release_receipts_keep_code_identity(monkeypatch):
    pin = implementation('biopipe-core')
    workflow = graph([operator('step')], mode='auto')
    workflow.plugin_lock = {'portable': pin}
    current = {**pin, 'sha256': 'new-index', 'declaration_sha': 'new-default'}
    descriptor = spec(origin='bundled', distribution='biopipe-core', version='1.0', implementation=current)
    assert targets(planner.make_plan(workflow, [host(specs=[descriptor])])) == {'step': LOCAL}
    current = {**current, 'code_sha': 'new-code'}
    descriptor['implementation'] = current
    with pytest.raises(GraphError, match='pinned implementation'):
        planner.make_plan(workflow, [host(specs=[descriptor])])
    monkeypatch.setattr(planner, 'released_replacements', lambda *_: {('portable', planner.identity(pin)): current})
    assert targets(planner.make_plan(workflow, [host(specs=[descriptor])])) == {'step': LOCAL}


def test_reader_pin_is_checked_on_the_destination():
    pin = implementation('custom-reader')
    workflow = graph([source(location=LOCAL), operator('step')], [('input', 'step')], mode='auto')
    workflow.plugin_lock = {'CsvReader': pin}
    changed = reader(origin='wheel', implementation={**pin, 'sha256': 'other'})
    exact = reader(origin='wheel', implementation=pin)
    assert targets(planner.make_plan(workflow, [host(readers=[changed]), host(SSH, 'linux', readers=[exact])])) == {'step': SSH}


def test_host_validated_historical_pin_allows_known_snapshot_migration_only():
    pin = implementation('biopipe-core', code='historical-code')
    workflow = graph([operator('step')], mode='auto')
    workflow.plugin_lock = {'portable': pin}
    current = spec(origin='bundled', distribution='biopipe-core', version='1.0',
                   implementation={**pin, 'code_sha': 'current-code', 'sha256': 'current-index'})
    info = host(specs=[current])
    with pytest.raises(GraphError, match='pinned implementation'):
        planner.make_plan(workflow, [info])
    info['validated_pins'] = {'portable': [{**pin, 'code_sha': 'different-history'}]}
    with pytest.raises(GraphError, match='pinned implementation'):
        planner.make_plan(workflow, [info])
    info['validated_pins'] = {'portable': [deepcopy(pin)]}
    assert targets(planner.make_plan(workflow, [info])) == {'step': LOCAL}
    info['dependencies'] = {'entries': [{'id': 'portable', 'status': 'failed'}]}
    with pytest.raises(GraphError, match='dependencies are not ready'):
        planner.make_plan(workflow, [info])
    info['dependencies'] = {}
    current['supported_systems'] = ['linux']
    with pytest.raises(GraphError, match='requires linux'):
        planner.make_plan(workflow, [info])


def test_validated_wheel_pin_is_scoped_to_the_verifying_host_and_operator():
    pin = implementation()
    workflow = graph([operator('step')], mode='auto')
    workflow.plugin_lock = {'portable': pin}
    current = spec(origin='wheel', implementation={**pin, 'sha256': 'new-wheel'})
    local = host(specs=[current], validated_pins={'unrelated': [pin]})
    remote = host(SSH, 'linux', [current], validated_pins={'portable': [pin]})
    assert targets(planner.make_plan(workflow, [local, remote])) == {'step': SSH}
    with pytest.raises(GraphError, match='pinned implementation'):
        planner.make_plan(workflow, [local])
