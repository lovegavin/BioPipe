"""Metadata-only task preflight using the same graph compiler as all clients."""
from copy import deepcopy
from pathlib import Path


def check_manifest(task_dir, manifest):
    from src.web.graph import compile_graph, import_manifest
    from src.web.operator_catalog import catalog_from_descriptors
    import yaml

    task_dir = Path(task_dir).resolve()
    value = deepcopy(manifest)
    errors, sources = [], {}
    for name, source in value.get('sources', {}).items():
        path = (task_dir / source['path']).resolve()
        if not path.is_file() and not path.is_dir():
            errors.append({'where': 'source:' + name, 'message': f'file not found: {path}'})
        sources[name] = {'path': str(path), 'reader': source.get('reader'),
                         'dims': source['dims'], 'exists': path.exists()}
    for step in value.get('steps', []):
        # Old exports can contain this engine-owned key. Edges reconstruct it.
        step.get('params', {}).pop('_input_names', None)
    steps = []
    if not errors:
        try:
            import json
            from operon.packages import bundled_state
            from operon.plugins import active_descriptors
            lock_path = task_dir / 'plugins.lock.json'
            state = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.is_file() else bundled_state(manifest_only=True)
            catalog = catalog_from_descriptors(active_descriptors(state))
            # An explicit local task may reference data outside its own folder,
            # including another drive. This allowance belongs to this CLI call;
            # the HTTP/Studio compiler keeps its default workspace policy.
            input_roots = {task_dir, *(Path(source['path']).parent for source in sources.values())}
            from operon.reader_selection import candidates
            def include_paths(spec, params, base):
                for key, field in spec.get('parameters_schema', {}).get('properties', {}).items():
                    path = params.get(key)
                    if field.get('x-operon-path') and isinstance(path, str) and path:
                        input_roots.add((base / path).resolve().parent)
            for source in value['sources'].values():
                for reader in candidates(catalog['readers'], source['path'], source.get('reader')):
                    include_paths(reader, source.get('args', {}), (task_dir / source['path']).resolve().parent)
            operators = {spec['id']: spec for spec in catalog['operators']}
            for step in value['steps']:
                include_paths(operators.get(step['name'], {}), step.get('params', {}), task_dir)
            graph = import_manifest(yaml.safe_dump(value, allow_unicode=True), '.', catalog, task_dir,
                                    input_roots=input_roots)
            compiled, _ = compile_graph(graph, catalog, task_dir, require_files=True,
                                        input_roots=input_roots)
            steps = [{'index': i, 'name': step['name'], 'inputs': step['inputs']}
                     for i, step in enumerate(compiled['steps'], 1)]
        except (ValueError, KeyError, TypeError) as error:
            errors.append({'where': 'workflow', 'message': str(error)})
    return {'ok': not errors, 'task_dir': str(task_dir), 'sources': sources, 'steps': steps, 'errors': errors}
