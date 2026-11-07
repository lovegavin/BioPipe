from copy import deepcopy
from types import SimpleNamespace

import pytest

from operon.documents import CommandError, DocumentHub


@pytest.fixture
def canvas(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.documents.analyze_graph', lambda *a, **k: {'nodes': {}, 'edges': []})
    mirrored = []
    service = SimpleNamespace(directory=tmp_path, root=tmp_path, base_catalog={},
        settings=SimpleNamespace(input_roots=[]), routes=SimpleNamespace(save_workspace=mirrored.append),
        plugins=SimpleNamespace(pin=lambda x: x, catalog_for=lambda *a: {}))
    hub = DocumentHub(service)
    graph = {'name': 'Example', 'nodes': [{'id': 'pca', 'kind': 'operator', 'operator': 'pca',
        'position': {'x': 0, 'y': 0}, 'params': {'n_components': 2, 'scale': False}}], 'edges': []}
    session = hub.create({'schema_version': 1, 'active_id': 'main', 'documents': [{'id': 'main', 'graph': graph}]})
    return hub, session['id']


def apply(hub, session, components, request='agent-1'):
    current = hub.get(session)
    return hub.apply(session, 'main', current['revision'], [
        {'op': 'update_node', 'id': 'pca', 'patch': {'params': {'n_components': components, 'scale': False}}}
    ], actor='agent:test', request_id=request)


def test_events_show_parameter_diff_and_retry_does_not_duplicate(canvas):
    hub, session = canvas
    first = apply(hub, session, 3)
    replay = apply(hub, session, 3)
    assert replay['replayed'] and replay['transaction_id'] == first['transaction_id']
    assert replay['revision'] == first['revision'] == 1
    result = hub.events(session, 0)
    assert result['next_cursor'] == 1 and len(result['events']) == 1
    event = result['events'][0]
    assert event['actor'] == 'agent:test'
    assert event['changes'][0]['path'] == ['nodes', 'pca', 'params', 'n_components']
    assert event['changes'][0]['before'] == '2' and event['changes'][0]['after'] == '3'
    assert event['affected'] == [{'document_id': 'main', 'nodes': ['pca']}]
    with pytest.raises(CommandError, match='Request ID'):
        apply(hub, session, 4)


def test_targeted_undo_preserves_later_human_parameter_and_position(canvas):
    hub, session = canvas
    first = apply(hub, session, 3)
    workspace = deepcopy(first['workspace'])
    workspace['documents'][0]['graph']['nodes'][0]['params']['scale'] = True
    workspace['documents'][0]['graph']['nodes'][0]['position']['x'] = 50
    human = hub.sync(session, workspace, first['revision'])
    restored = hub.undo(session, 'main', human['revision'], transaction_id=first['transaction_id'])
    node = restored['workspace']['documents'][0]['graph']['nodes'][0]
    assert node['params'] == {'n_components': 2, 'scale': True}
    assert node['position']['x'] == 50
    redone = hub.undo(session, 'main', restored['revision'], redo=True, transaction_id=first['transaction_id'])
    assert redone['workspace']['documents'][0]['graph']['nodes'][0]['params'] == {'n_components': 3, 'scale': True}


def test_targeted_undo_rejects_overlap_without_mutation(canvas):
    hub, session = canvas
    first = apply(hub, session, 3)
    workspace = deepcopy(first['workspace'])
    workspace['documents'][0]['graph']['nodes'][0]['params']['n_components'] = 8
    human = hub.sync(session, workspace, first['revision'])
    with pytest.raises(CommandError) as failure:
        hub.undo(session, 'main', human['revision'], transaction_id=first['transaction_id'])
    assert failure.value.code == 'undo_conflict'
    assert hub.get(session)['revision'] == 2
    assert hub.get(session)['workspace'] == human['workspace']


def test_revision_conflict_is_atomic_and_presence_is_not_scientific_revision(canvas):
    hub, session = canvas
    hub.presence(session, {'document_id': 'main', 'nodes': ['pca']})
    assert hub.get(session)['revision'] == 0
    apply(hub, session, 3)
    before = hub.get(session)
    with pytest.raises(CommandError) as failure:
        hub.apply(session, 'main', 0, [{'op': 'configure', 'patch': {'name': 'Stale'}}])
    assert failure.value.code == 'revision_conflict'
    assert hub.get(session) == before


def test_paginated_events_never_skip_and_expired_cursor_requests_resync(canvas):
    hub, session = canvas
    for i in range(5):
        apply(hub, session, i + 3, request=f'edit-{i}')
    first = hub.events(session, 0, 2)
    assert first['seq'] == 5 and first['next_cursor'] == 2 and first['has_more']
    second = hub.events(session, first['next_cursor'], 2)
    assert [x['seq'] for x in second['events']] == [3, 4]
    with hub.lock:
        state = hub.load(session)
        state['events'] = state['events'][-2:]
        hub.save(state)
    assert hub.events(session, 0)['reset']
    assert hub.events(session, 99)['reset']
    with pytest.raises(CommandError):
        hub.events(session, -1)


def test_event_values_bounded_and_full_detail_is_on_demand(canvas):
    hub, session = canvas
    changed = hub.apply(session, 'main', 0, [{'op': 'configure', 'patch': {'params': {'code': 'x' * 10000}}}])
    brief = hub.events(session, 0)['events'][0]['changes'][0]
    assert len(brief['after']) == 160 and brief['after_truncated']
    detail = hub.diff(session, changed['transaction_id'])
    assert len(detail['changes'][0]['after']) == 1600 and detail['changes'][0]['after_truncated']
    # Restarting a hub retains authoritative state, event cursor and diff.
    restored = DocumentHub(hub.service)
    assert restored.get(session)['workspace'] == changed['workspace']
    assert restored.diff(session, changed['transaction_id']) == detail


def test_legacy_latest_undo_still_works(canvas):
    hub, session = canvas
    changed = apply(hub, session, 3)
    with hub.lock:
        state = hub.load(session)
        state['history']['main']['past'][0].pop('changes')
        hub.save(state)
    result = hub.undo(session, 'main', changed['revision'])
    assert result['workspace']['documents'][0]['graph']['nodes'][0]['params']['n_components'] == 2


def test_order_is_part_of_the_transaction_and_reordering_never_erases_later_edits():
    from operon.document_changes import changes, compensate
    before = {'nodes': [{'id': 'a', 'params': {}}, {'id': 'b', 'params': {}}]}
    after = {'nodes': list(reversed(deepcopy(before['nodes'])))}
    delta = changes(before, after)
    restored, conflicts = compensate(after, delta)
    assert not conflicts and restored == before
    later = deepcopy(after)
    later['nodes'][0]['params']['human'] = 1
    _, conflicts = compensate(later, delta)
    assert conflicts == [['nodes']]


def test_undo_added_node_refuses_to_orphan_a_later_connection(canvas):
    hub, session = canvas
    state = hub.apply(session, 'main', 0, [{'op': 'add_node', 'node': {
        'id': 'new', 'kind': 'operator', 'operator': 'scale', 'params': {}, 'position': {'x': 20, 'y': 20}}}], actor='agent:test')
    workspace = deepcopy(state['workspace'])
    workspace['documents'][0]['graph']['edges'].append({'id': 'late', 'source': 'pca', 'target': 'new', 'sourceHandle': 'out', 'targetHandle': 'in-0'})
    later = hub.sync(session, workspace, state['revision'])
    with pytest.raises(CommandError, match='Later connections'):
        hub.undo(session, 'main', later['revision'], transaction_id=state['transaction_id'])
    assert hub.get(session)['workspace'] == later['workspace']
