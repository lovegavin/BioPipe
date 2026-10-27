from src.web.execution import execution_progress


def test_live_steps_include_nested_routes_and_parallel_children():
    job = {'status': 'running', 'graph': {'nodes': [
        {'id': 'a', 'kind': 'operator'},
        {'id': 'route', 'kind': 'route', 'route': {'graph': {'nodes': [
            {'id': 'inner1', 'kind': 'operator'}, {'id': 'inner2', 'kind': 'operator'}]}}},
        {'id': 'b', 'kind': 'operator'}]},
        'execution_plan': {'units': [{'id': 'one', 'node_ids': ['a', 'route']}, {'id': 'two', 'node_ids': ['b']}]},
        'completed_units': [], 'children': [
            {'unit_id': 'one', 'status': 'running', 'progress': {'completed': 2, 'total': 3, 'current': 'inner2'}},
            {'unit_id': 'two', 'status': 'running', 'progress': {'completed': 0, 'total': 1, 'current': 'b'}}],
        'progress': {'phase': 'running', 'completed': 0, 'total': 2}}
    progress = execution_progress(job)
    assert (progress['completed'], progress['total'], progress['percent']) == (2, 4, 50)
    assert progress['current'] == 'inner2, b'
    job['progress'] = {'phase': 'downloading', 'bytes_done': 5, 'bytes_total': 10, 'current': 'matrix.npy'}
    progress = execution_progress(job)
    assert progress['current'] == 'matrix.npy' and progress['bytes_done'] == 5
    job['status'] = 'complete'
    job['completed_units'] = ['one', 'two']
    assert execution_progress(job)['completed'] == 4
    assert execution_progress(job)['percent'] == 100
