"""Public workflow YAML. Static translation into the application's existing Graph.

No operator modules, scientific dependencies or services are imported to lint or
format a document. Actual prepare/validate/run remain application operations.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import re

import yaml

FORMAT = 'biopipe.workflow'
_ID = re.compile(r'^[A-Za-z_][A-Za-z0-9_.-]{0,79}$')


class WorkflowError(ValueError):
    code = 'invalid_workflow'


class WorkflowResourceError(WorkflowError):
    code = 'workflow_resource_error'

    def __init__(self, path, directory, reason, explanation):
        directory = Path(directory).resolve()
        resource = Path(path).relative_to(directory).as_posix()
        self.details = {'resource': resource, 'directory': str(directory), 'reason': reason}
        super().__init__(f'Workflow file "{resource}": {explanation}. '
                         f'Expected project base directory: {directory}. '
                         'Keep the YAML and its referenced JSON/script files together; '
                         'select their project base directory and retry. For GUI import, '
                         'place the project inside the workspace or import a complete workflow ZIP.')


def _resource_text(path, directory):
    try:
        if path.is_dir():
            raise WorkflowResourceError(path, directory, 'not_file', 'a directory was selected instead of a file')
        return path.read_text(encoding='utf-8-sig')
    except FileNotFoundError as error:
        raise WorkflowResourceError(path, directory, 'missing', 'file not found') from error
    except UnicodeError as error:
        raise WorkflowResourceError(path, directory, 'encoding', 'the file must be UTF-8 text') from error
    except OSError as error:
        raise WorkflowResourceError(path, directory, 'unreadable', 'cannot read this file; check access permissions') from error


class WorkflowLoader(yaml.SafeLoader):
    # YAML 1.2 booleans: sample IDs "on" and "off" must remain strings.
    yaml_implicit_resolvers = {
        key: [(tag, exp) for tag, exp in values if tag not in
              ('tag:yaml.org,2002:bool', 'tag:yaml.org,2002:timestamp')]
        for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise WorkflowError('YAML aliases are not supported; use explicit workflow nodes')
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise WorkflowError('Mapping keys must be strings')
            if key in result:
                raise WorkflowError(f'Duplicate YAML key: {key}')
            result[key] = self.construct_object(value_node, deep=deep)
        return result


WorkflowLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false|True|False|TRUE|FALSE)$'), list('tTfF'))


def _mapping(value, allowed, where, required=()):
    if not isinstance(value, dict):
        raise WorkflowError(f'{where} must be an object')
    if set(value) - set(allowed):
        raise WorkflowError(f'Unknown {where} fields: {sorted(set(value) - set(allowed))}')
    if set(required) - set(value):
        raise WorkflowError(f'Missing {where} fields: {sorted(set(required) - set(value))}')
    return value


def parse(text):
    try:
        value = yaml.load(text, Loader=WorkflowLoader)
        json.dumps(value, allow_nan=False)
    except (yaml.YAMLError, TypeError, RecursionError) as error:
        raise WorkflowError(f'Invalid workflow YAML: {error}') from error
    if not isinstance(value, dict):
        raise WorkflowError('Workflow must be a mapping')
    return value


def _json(path, directory):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise WorkflowError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    text = _resource_text(path, directory)
    try:
        return json.loads(text, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(WorkflowError(f'Invalid JSON constant {value}')))
    except json.JSONDecodeError as error:
        raise WorkflowResourceError(path, directory, 'invalid_json',
                                    f'invalid JSON at line {error.lineno}, column {error.colno}') from error


def _sidecar(spec, key, directory, default):
    if key in spec and key + '_file' in spec:
        raise WorkflowError(f'Use {key} or {key}_file, not both')
    if key + '_file' in spec:
        value = spec[key + '_file']
        if not isinstance(value, str) or not value:
            raise WorkflowError(f'{key}_file must be a path')
        return _json(resolve_resource(directory, value), directory)
    return deepcopy(spec.get(key, default))


def resolve_resource(directory, value):
    """Metadata and source assets belong to the project, unlike input data."""
    if not isinstance(value, str) or not value or Path(value).is_absolute() or ':' in value or '\\' in value:
        raise WorkflowError('Workflow resources must use contained relative paths')
    root = Path(directory).resolve()
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise WorkflowError('Workflow resource escapes the project directory')
    return path


def compile_spec(spec, directory):
    """Return Graph data without resolving library defaults or touching inputs."""
    from src.web.models import Graph
    directory = Path(directory).resolve()
    _mapping(spec, {'format', 'schema_version', 'name', 'sources', 'steps', 'outputs',
                    'parameters', 'parameters_file', 'execution', 'execution_file',
                    'lock_file', 'ui_file'}, 'workflow', ('format', 'schema_version', 'sources', 'steps'))
    if spec['format'] != FORMAT or type(spec['schema_version']) is not int or spec['schema_version'] != 1:
        raise WorkflowError('Expected biopipe.workflow schema_version 1')
    sources, steps = spec['sources'], spec['steps']
    if not isinstance(sources, dict) or not isinstance(steps, dict):
        raise WorkflowError('sources and steps must be mappings keyed by stable node IDs')
    if set(sources) & set(steps):
        raise WorkflowError('Source and step node IDs must be globally unique')
    for key in (*sources, *steps):
        if not _ID.fullmatch(key):
            raise WorkflowError(f'Invalid node ID: {key}')
    parameters = _sidecar(spec, 'parameters', directory, {})
    execution = _sidecar(spec, 'execution', directory, {})
    _mapping(parameters, {'format', 'schema_version', 'sources', 'steps', 'params'}, 'parameters')
    if parameters.get('format', 'biopipe.workflow-parameters') != 'biopipe.workflow-parameters' or type(parameters.get('schema_version', 1)) is not int or parameters.get('schema_version', 1) != 1:
        raise WorkflowError('Unsupported parameters schema')
    for kind, items in (('sources', sources), ('steps', steps)):
        values = parameters.get(kind, {})
        if not isinstance(values, dict) or set(values) - set(items):
            raise WorkflowError(f'Parameter {kind} must reference existing node IDs')
    _mapping(execution, {'format', 'schema_version', 'memory', 'runtime', 'manifest_extra', 'interface'}, 'execution')
    if execution.get('format', 'biopipe.workflow-execution') != 'biopipe.workflow-execution' or type(execution.get('schema_version', 1)) is not int or execution.get('schema_version', 1) != 1:
        raise WorkflowError('Unsupported execution schema')
    nodes, edges = [], []
    for ordinal, (key, source) in enumerate(sources.items()):
        source = deepcopy(source)
        _mapping(source, {'path', 'reader', 'dims', 'labels', 'location', 'title'}, f'source {key}', ('path',))
        title = source.pop('title', '')
        vals = parameters.get('sources', {}).get(key, {})
        _mapping(vals, {'args', 'params', 'context_params'}, f'source parameters {key}')
        source['args'] = deepcopy(vals.get('args', {}))
        # Remote paths retain their server namespace. Local paths resolve at
        # the declaring document, independent of the caller's cwd/profile.
        if (source.get('location') or {}).get('kind') != 'ssh' and source['path']:
            source['path'] = str((directory / source['path']).resolve())
        nodes.append({'id': key, 'kind': 'source', 'source': source, 'title': title,
                      'params': vals.get('params', {}), 'context_params': vals.get('context_params', {}),
                      'position': {'x': 60, 'y': 80 + ordinal * 210}})

    def reference(value):
        if not isinstance(value, str):
            raise WorkflowError('Input references must be strings or bindings with from')
        if value.startswith('sources.') and value[8:] in sources:
            return value[8:], 'out'
        if value.startswith('steps.'):
            node, _, port = value[6:].rpartition('.')
            if node in steps and re.fullmatch(r'out(?:-\d+)?', port):
                return node, port
        raise WorkflowError(f'Invalid or undefined output reference: {value}')

    for ordinal, (key, step) in enumerate(steps.items()):
        _mapping(step, {'operator', 'route', 'script', 'inputs', 'title', 'input_count'}, f'step {key}', ('inputs',))
        kinds = [kind for kind in ('operator', 'route', 'script') if kind in step]
        if len(kinds) != 1:
            raise WorkflowError(f'{key} requires exactly one operator, route or script')
        kind = kinds[0]
        vals = parameters.get('steps', {}).get(key, {})
        _mapping(vals, {'params', 'context_params', 'route'}, f'step parameters {key}')
        payload = deepcopy(step[kind])
        if kind == 'script' and isinstance(payload, str):
            from .script_operators import inspect_source
            path = resolve_resource(directory, payload)
            try:
                payload = inspect_source(path.name, _resource_text(path, directory))
            except SyntaxError as error:
                raise WorkflowResourceError(path, directory, 'invalid_script',
                                            f'invalid script syntax at line {error.lineno}, column {error.offset}') from error
        elif kind == 'script':
            from .script_operators import validate_script
            payload = validate_script(payload)
        node = {'id': key, 'kind': kind, kind: payload, 'title': step.get('title', ''),
                'params': vals.get('params', {}), 'context_params': vals.get('context_params', {}),
                'input_count': step.get('input_count', 1), 'position': {'x': 360, 'y': 80 + ordinal * 210}}
        if kind == 'route' and 'route' in vals:
            from src.web.parameters import restore_graph
            node['route']['graph'] = restore_graph(node['route']['graph'], vals['route']).model_dump(mode='json')
        nodes.append(node)
        if not isinstance(step['inputs'], dict):
            raise WorkflowError(f'{key}.inputs must be a mapping')
        occupied = set()
        for port, binding in step['inputs'].items():
            if not re.fullmatch(r'in-?\d+', port):
                raise WorkflowError(f'Unsupported input port {port}; use in0, in1, ...')
            handle = 'in-' + str(int(port.removeprefix('in').lstrip('-')))
            if handle in occupied:
                raise WorkflowError(f'Duplicate target port: {key}.{handle}')
            occupied.add(handle)
            extra = {}
            if isinstance(binding, dict):
                _mapping(binding, {'from', 'adaptation', 'id'}, 'input binding', ('from',))
                extra = {k: deepcopy(v) for k, v in binding.items() if k != 'from'}
                binding = binding['from']
            origin, output = reference(binding)
            edges.append({'id': f'{origin}-{output}-{key}-{handle}', 'source': origin,
                          'target': key, 'sourceHandle': output, 'targetHandle': handle, **extra})
    outputs = spec.get('outputs', {})
    if not isinstance(outputs, dict):
        raise WorkflowError('outputs must be a mapping')
    for value in outputs.values():
        reference(value)
    # Cycle checks are independent of optional scientific packages/catalogs.
    degree = {node['id']: 0 for node in nodes}
    followers = {key: [] for key in degree}
    for edge in edges:
        degree[edge['target']] += 1
        followers[edge['source']].append(edge['target'])
    queue = [key for key, count in degree.items() if count == 0]
    seen = 0
    while queue:
        key = queue.pop()
        seen += 1
        for follower in followers[key]:
            degree[follower] -= 1
            if degree[follower] == 0:
                queue.append(follower)
    if seen != len(nodes):
        raise WorkflowError('Workflow contains a cycle')
    runtime = deepcopy(execution.get('runtime', {}))
    if outputs:
        runtime['workflow_outputs'] = deepcopy(outputs)
    graph = {'schema_version': 2, 'name': spec.get('name', 'Workflow'), 'base_dir': '.',
             'nodes': nodes, 'edges': edges, 'params': parameters.get('params', {}),
             'memory': execution.get('memory', {'enabled': True, 'auto_spill': True}),
             'runtime': runtime, 'manifest_extra': execution.get('manifest_extra', {}),
             'interface': execution.get('interface')}
    if 'lock_file' in spec:
        lock = _json(resolve_resource(directory, spec['lock_file']), directory)
        _mapping(lock, {'format', 'schema_version', 'plugin_lock'}, 'lock', ('format', 'schema_version', 'plugin_lock'))
        if lock['format'] != 'biopipe.workflow-lock' or lock['schema_version'] != 1:
            raise WorkflowError('Unsupported lock schema')
        graph['plugin_lock'] = lock['plugin_lock']
    if 'ui_file' in spec:
        ui = _json(resolve_resource(directory, spec['ui_file']), directory)
        _mapping(ui, {'positions'}, 'ui')
        if not isinstance(ui.get('positions', {}), dict) or set(ui.get('positions', {})) - set(degree):
            raise WorkflowError('UI positions reference missing nodes')
        for node in nodes:
            node['position'] = ui.get('positions', {}).get(node['id'], node['position'])
    result = Graph.model_validate(graph).model_dump(mode='json')
    json.dumps(result, allow_nan=False)
    return result


def load_workflow(path):
    path = Path(path).resolve()
    return compile_spec(parse(_resource_text(path, path.parent)), path.parent)


def format_workflow(path, *, check=False):
    path = Path(path).resolve()
    original = _resource_text(path, path.parent)
    spec = parse(original)
    compile_spec(spec, path.parent)
    text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)
    changed = text != original
    if changed and not check:
        import tempfile
        # The formatting operation cannot alter parameter or execution files.
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as file:
                file.write(text)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'path': str(path), 'changed': changed, 'check': check}


def export_workflow(graph, directory):
    """Write a new public project; never overwrite an existing project."""
    from src.web.models import Graph
    from src.web.parameters import split_graph
    from src.web.storage import atomic_json
    graph = Graph.model_validate(graph).model_dump(mode='json')
    directory = Path(directory).resolve()
    if directory.exists() and any(directory.iterdir()):
        raise WorkflowError('Export directory must be empty; existing files were preserved')
    directory.mkdir(parents=True, exist_ok=True)
    topology, values = split_graph(graph)
    spec = {'format': FORMAT, 'schema_version': 1, 'name': graph['name'],
            'parameters_file': 'parameters.json', 'execution_file': 'execution.json',
            'lock_file': 'workflow.lock.json', 'ui_file': 'ui.json', 'sources': {}, 'steps': {},
            'outputs': deepcopy(graph['runtime'].get('workflow_outputs', {}))}
    parameters = {'format': 'biopipe.workflow-parameters', 'schema_version': 1,
                  'params': values['params'], 'sources': {}, 'steps': {}}
    for node in topology['nodes']:
        key, kind = node['id'], node['kind']
        entry = values['nodes'][key]
        if kind == 'source':
            source = deepcopy(node['source'])
            if (source.get('location') or {}).get('kind') != 'ssh' and source['path']:
                path = Path(graph['base_dir']) / source['path']
                if path.is_absolute():
                    try:
                        source['path'] = Path(os.path.relpath(path, directory)).as_posix()
                    except ValueError:
                        source['path'] = str(path)
            source['title'] = node['title']
            spec['sources'][key] = source
            parameters['sources'][key] = {k: entry[k] for k in ('args', 'params', 'context_params')}
        else:
            spec['steps'][key] = {kind: deepcopy(node[kind]), 'title': node['title'],
                                  'input_count': node['input_count'], 'inputs': {}}
            parameters['steps'][key] = {k: entry[k] for k in ('params', 'context_params', 'route') if k in entry}
    kinds = {node['id']: node['kind'] for node in graph['nodes']}
    for edge in graph['edges']:
        prefix = 'sources.' if kinds[edge['source']] == 'source' else 'steps.'
        reference = prefix + edge['source'] + ('' if prefix == 'sources.' else '.' + edge['sourceHandle'])
        binding = {'from': reference, 'id': edge['id']}
        if edge.get('adaptation') is not None:
            binding['adaptation'] = deepcopy(edge['adaptation'])
        spec['steps'][edge['target']]['inputs'][edge['targetHandle']] = binding
    runtime = deepcopy(graph['runtime'])
    runtime.pop('workflow_outputs', None)
    execution = {'format': 'biopipe.workflow-execution', 'schema_version': 1,
                 'memory': graph['memory'], 'runtime': runtime,
                 'manifest_extra': graph['manifest_extra'], 'interface': graph['interface']}
    atomic_json(directory / 'parameters.json', parameters)
    atomic_json(directory / 'execution.json', execution)
    atomic_json(directory / 'workflow.lock.json', {'format': 'biopipe.workflow-lock', 'schema_version': 1, 'plugin_lock': graph['plugin_lock']})
    atomic_json(directory / 'ui.json', {'positions': {node['id']: node['position'] for node in graph['nodes']}})
    (directory / 'workflow.yaml').write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding='utf-8')
    return {'path': str(directory / 'workflow.yaml'), 'files': ['workflow.yaml', 'parameters.json', 'execution.json', 'workflow.lock.json', 'ui.json']}


def init_workflow(directory):
    directory = Path(directory).resolve()
    graph = {'name': 'CSV PCA', 'nodes': [
        {'id': 'matrix', 'kind': 'source', 'position': {'x': 60, 'y': 80},
         'source': {'path': str(directory / 'data/matrix.csv'), 'reader': 'CsvReader',
                    'dims': ['sample', 'feature'], 'labels': {'sample': {'feature': 0}, 'feature': 'builtin'},
                    'args': {'header': True}}},
        {'id': 'pca_main', 'kind': 'operator', 'operator': 'pca', 'position': {'x': 360, 'y': 80},
         'params': {'dim': 'feature', 'n_components': 2}}],
        'edges': [{'id': 'matrix-pca', 'source': 'matrix', 'target': 'pca_main'}]}
    result = export_workflow(graph, directory)
    (directory / 'data').mkdir()
    (directory / 'data/matrix.csv').write_text('sample,a,b,c\ns1,1,2,3\ns2,2,3,4\ns3,4,1,2\ns4,3,4,1\n', encoding='utf-8')
    return result


def json_schema():
    """Authoring structure schema; port/library checks remain compile-time."""
    def obj(properties, required=()):
        return {'type': 'object', 'additionalProperties': False, 'properties': properties,
                'required': list(required)}
    text = {'type': 'string'}
    source = obj({key: {} for key in ('path', 'reader', 'dims', 'labels', 'location', 'title')}, ['path'])
    source['properties']['path'] = text
    binding = {'oneOf': [text, obj({'from': text, 'id': text, 'adaptation': {'type': 'object'}}, ['from'])]}
    step = obj({'operator': text, 'route': {'type': 'object'}, 'script': {'type': ['string', 'object']},
                'inputs': {'type': 'object', 'propertyNames': {'pattern': '^in-?[0-9]+$'}, 'additionalProperties': binding},
                'title': text, 'input_count': {'type': 'integer', 'minimum': 0, 'maximum': 20}}, ['inputs'])
    step['oneOf'] = [{'required': [key]} for key in ('operator', 'route', 'script')]
    schema = obj({'format': {'const': FORMAT}, 'schema_version': {'const': 1, 'type': 'integer'},
                  'name': text, 'sources': {'type': 'object', 'additionalProperties': source},
                  'steps': {'type': 'object', 'additionalProperties': step},
                  'outputs': {'type': 'object', 'additionalProperties': text},
                  'parameters': {'type': 'object'}, 'parameters_file': text,
                  'execution': {'type': 'object'}, 'execution_file': text,
                  'lock_file': text, 'ui_file': text}, ['format', 'schema_version', 'sources', 'steps'])
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
    schema['title'] = 'BioPipe workflow v1'
    schema['allOf'] = [{'not': {'required': [key, key + '_file']}} for key in ('parameters', 'execution')]
    return schema
