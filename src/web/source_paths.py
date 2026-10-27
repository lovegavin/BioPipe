"""Source metadata routing without inspecting a remote path on the editor host."""
from biopipe.file_formats import primary_ext, uncompressed_path


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


def source_candidates(graph, catalog, root, value, location=None):
    from .graph import project_path
    if hasattr(location, 'model_dump'):
        location = location.model_dump()
    if (location and location.get('kind') == 'ssh') or (not location and remote_profile(graph)):
        return [r for r in catalog['readers'] if primary_ext(value) in r['extensions']]
    path = project_path(root, value, graph.base_dir)
    primary = uncompressed_path(path)
    return [r for r in catalog['readers'] if primary_ext(path) in r['extensions']
            and (not path.is_file() or (all(primary.with_suffix(s).exists() for s in r.get('requires_siblings', []))
            and not any(primary.with_suffix(s).exists() for s in r.get('excludes_siblings', []))))]
