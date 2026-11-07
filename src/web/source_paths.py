"""Source metadata routing without inspecting a remote path on the editor host."""
def remote_profile(graph):
    target = graph.runtime.get('execution', {})
    if isinstance(target, dict) and target.get('kind') == 'ssh':
        key = target.get('profile_id')
        if not isinstance(key, str) or not key:
            raise ValueError('Choose a server connection for this workflow')
        return key
    if target and (not isinstance(target, dict) or target.get('kind', 'local') != 'local'):
        raise ValueError('Unknown workflow execution target')
    return None


def source_candidates(graph, catalog, root, value, location=None, reader_id=None, *, input_roots=None):
    from .graph import input_path
    from operon.reader_selection import candidates, prefer_typed

    def select(value, **options):
        found = candidates(catalog['readers'], value, reader_id, **options)
        return found if reader_id else prefer_typed(found)

    if hasattr(location, 'model_dump'):
        location = location.model_dump()
    if (location and location.get('kind') == 'ssh') or (not location and remote_profile(graph)):
        return select(value)
    if not value:
        return select(value)
    path = input_path(root, value, graph.base_dir, input_roots)
    return select(path, check_siblings=path.is_file())
