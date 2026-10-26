"""Protocol v3 declarations: static authoring, content identities and binding.

Only ``load_class`` imports implementation code. All other operations are data
or source-byte inspection, safe for maintenance and the service process.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import importlib
import inspect
import ast
import json
from pathlib import Path

DECLARATION_ATTRIBUTES = {
    'name', 'version', 'title', 'description', 'category', 'icon', 'preview',
    'title_aliases', 'title_parameter', 'parameters_schema', 'ui_defaults',
    'input_contracts', 'output_contract', 'inputs_arity', 'outputs', 'output_parameter',
    'supports_streaming', 'supports_cuda', 'stream_protocol', 'stream_buffer_multiplier',
    'stream_fixed_bytes', 'supports_disk_read', 'disk_protocol', 'dependencies',
    'dependency_imports', 'extensions', 'requires_siblings', 'excludes_siblings',
    'handles_compression', 'file_input', 'builtin_package', 'legacy_parameters',
}


def definitions(document):
    if document.get('protocol_version') != 3:
        raise ValueError('Protocol v3 descriptors are required; run the explicit migration first')
    return [d for p in document['packages'] for d in p['descriptors']] if 'packages' in document else document['descriptors']


def source_declarations(path, module):
    """Each implementation owns a literal definition and its parameter JSON.

    Reading the AST never executes module-level imports or expressions.
    """
    path = Path(path)
    tree = ast.parse(path.read_text(encoding='utf-8'))
    base_names = {'Step', 'Operator', 'Reader'}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            base_names.update(a.asname or a.name for a in node.names if a.name in {'Step', 'Operator', 'Reader'})
    result = []
    parameter_owners = {}
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        fields = {}
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {'definition', 'parameters_file', 'provider'}:
                    try:
                        fields[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError) as exc:
                        raise ValueError(f'{cls.name}.{target.id} must be literal data') from exc
        if 'definition' not in fields:
            bases = {ast.unparse(b).split('.')[-1] for b in cls.bases}
            if bases & base_names:
                raise ValueError(f'{cls.name}: protocol v3 requires definition + a parameter JSON file; migrate the class declaration')
            continue
        value = fields['definition']
        if not isinstance(value, dict) or 'parameters_schema' in value:
            raise ValueError(f'{cls.name}: definition must be an object; parameters belong in the separate JSON')
        relative = fields.get('parameters_file', 'parameters.json' if path.stem == '__init__' else path.stem + '.parameters.json')
        if not isinstance(relative, str) or Path(relative).is_absolute() or ':' in relative:
            raise ValueError('parameters_file must be a local relative JSON path')
        parameter_path = (path.parent / relative.replace('\\', '/')).resolve()
        if not parameter_path.is_relative_to(path.parent.resolve()) or parameter_path.suffix != '.json':
            raise ValueError('parameters_file must remain inside the implementation directory')
        if parameter_path in parameter_owners:
            raise ValueError(f'{cls.name}: parameter JSON already belongs to {parameter_owners[parameter_path]}; give each class its own file')
        parameter_owners[parameter_path] = cls.name
        schema = json.loads(parameter_path.read_text(encoding='utf-8'))
        result.append({**value, 'entry_point': module + ':' + cls.name,
                       'parameters_schema': schema, 'provider': fields.get('provider')})
    return result


def declaration_hash(value):
    from .protocol import Descriptor
    keys = set(Descriptor.model_fields) - {'code_sha', 'declaration_sha'}
    content = {k: v for k, v in value.items() if k in keys}
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def code_files(entry, root):
    root = Path(root)
    module = entry.split(':')[0]
    if module.startswith(('src.task.step.steps.', 'src.reader.readers.')):
        folders = [root / 'src/task/step/steps', root / 'src/reader/readers']
        return sorted(p for folder in folders for p in folder.rglob('*.py') if '__pycache__' not in p.parts)
    top = root / module.split('.')[0]
    return sorted(top.rglob('*.py')) if top.is_dir() else [top.with_suffix('.py')]


def code_hash(entry, root):
    root = Path(root).resolve()
    paths = code_files(entry, root)
    if not paths:
        raise ValueError(f'No implementation sources: {entry}')
    stamps = tuple((p.relative_to(root).as_posix(), p.stat().st_mtime_ns, p.stat().st_ctime_ns, p.stat().st_size) for p in paths)
    return _code_hash(str(root), stamps)


@lru_cache(maxsize=128)
def _code_hash(root, stamps):
    digest = hashlib.sha256()
    for relative, *_ in stamps:
        digest.update(relative.encode() + b'\0')
        digest.update((Path(root) / relative).read_text(encoding='utf-8').encode('utf-8'))
    return digest.hexdigest()


def compile_declaration(value, root):
    """Resolve assets and stamp source+declaration identities without imports."""
    from .protocol import Descriptor, validate_schema, validate_output_rule, validate_port_rule
    from .icons import is_image_icon, icon_path, image_data
    value = deepcopy(value)
    value.pop('provider', None)
    value.pop('code_sha', None)
    value.pop('declaration_sha', None)
    module = value['entry_point'].split(':')[0]
    source = Path(root) / (module.replace('.', '/') + '.py')
    if not source.is_file():
        source = Path(root) / module.replace('.', '/') / '__init__.py'
    if not source.is_file():
        raise ValueError(f'Implementation does not exist: {module}')
    if is_image_icon(value.get('icon')):
        value['icon_image'] = image_data(icon_path(source.parent, value['icon']))
    else:
        value.pop('icon_image', None)
    validate_schema(value['parameters_schema'])
    contracts = value['contracts']
    if value['kind'] == 'operator':
        arity = value.get('inputs_arity', 0)
        if arity != '*' and (type(arity) is not int or not 0 <= arity <= 20):
            raise ValueError('inputs_arity must be an integer from 0 to 20 or *')
        if len(contracts['inputs']) != (1 if arity == '*' else arity):
            raise ValueError('Declare one input contract per port')
        for port in contracts['inputs']:
            validate_port_rule(port)
        validate_output_rule(contracts['output'])
    else:
        validate_port_rule(contracts['output'])
        if not value.get('extensions'):
            raise ValueError('Readers must declare extensions')
        clsname = value['entry_point'].split(':')[1]
        cls = next((n for n in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(n, ast.ClassDef) and n.name == clsname), None)
        if cls and any(isinstance(n, ast.FunctionDef) and n.name == 'probe' for n in cls.body):
            value['resources']['probe'] = True
    value['code_sha'] = code_hash(value['entry_point'], root)
    value['declaration_sha'] = '0' * 64
    value = Descriptor.model_validate(value).model_dump(exclude_unset=True)
    value['declaration_sha'] = declaration_hash(value)
    from .protocol import validate_declaration
    validate_declaration(value)
    return Descriptor.model_validate(value).model_dump(exclude_unset=True)


def verify_declaration(descriptor):
    if descriptor.get('declaration_sha') != declaration_hash(descriptor):
        raise ValueError(f"Declaration hash mismatch: {descriptor['id']}")


def implementation_root(entry):
    """Find a provider on sys.path without importing its package __init__."""
    import sys
    relative = entry.split(':')[0].replace('.', '/')
    for item in sys.path:
        root = Path(item or '.').resolve()
        if (root / (relative + '.py')).is_file() or (root / relative / '__init__.py').is_file():
            return root
    raise ValueError(f'Implementation is not installed: {entry}')


def verify_code(descriptor, root=None):
    verify_declaration(descriptor)
    identity = descriptor.get('implementation')
    if identity and any(identity.get(k) != descriptor.get(k) for k in ('code_sha', 'declaration_sha')):
        raise ValueError(f"Runtime identity mismatch: {descriptor['id']}")
    root = Path(root) if root else implementation_root(descriptor['entry_point'])
    if descriptor.get('code_sha') != code_hash(descriptor['entry_point'], root):
        raise ValueError(f"Implementation code hash mismatch: {descriptor['id']}; rebuild or refresh the provider")


def bind_class(cls, descriptor):
    """Return a snapshot-specific subclass; never mutate another job's defaults."""
    from .protocol import validate_extension, Descriptor
    verify_declaration(descriptor)
    if not isinstance(cls, type):
        raise ValueError('Implementation entry must be a class')
    conflict = DECLARATION_ATTRIBUTES.intersection(cls.__dict__)
    if conflict and '_declaration' not in cls.__dict__:
        raise ValueError(f'{cls.__name__}: use definition + a separate parameter JSON: {sorted(conflict)}')
    Descriptor.model_validate({k: v for k, v in descriptor.items() if k in Descriptor.model_fields})
    attributes = {k: deepcopy(v) for k, v in descriptor.items() if k in DECLARATION_ATTRIBUTES}
    resources = descriptor['resources']
    attributes.update(name=descriptor['id'], input_contracts=deepcopy(descriptor['contracts']['inputs']),
                      output_contract=deepcopy(descriptor['contracts']['output']),
                      supports_streaming='stream' in resources['memory_modes'],
                      supports_disk_read='disk' in resources['memory_modes'],
                      _declaration={k: deepcopy(v) for k, v in descriptor.items() if k in Descriptor.model_fields}, __module__=cls.__module__)
    attributes.update({k: deepcopy(v) for k, v in resources.items() if k in DECLARATION_ATTRIBUTES})
    bound = type(cls.__name__, (cls,), attributes)
    validate_extension(bound, descriptor['kind'])
    return bound


def load_class(descriptor):
    verify_code(descriptor)
    module, name = descriptor['entry_point'].split(':', 1)
    return bind_class(getattr(importlib.import_module(module), name), descriptor)


def for_class(cls):
    if '_declaration' in cls.__dict__:
        return deepcopy(cls._declaration)
    path = Path(inspect.getfile(cls)).resolve()
    entry = cls.__module__ + ':' + cls.__name__
    root = implementation_root(entry)
    found = [d for d in source_declarations(path, cls.__module__) if d['entry_point'] == entry]
    if len(found) != 1:
        raise ValueError(f'{entry}: define the operator protocol and its parameter JSON')
    return compile_declaration(found[0], root)


def verify_archive(entries, descriptors):
    """Check the actual wheel bytes before installation or metadata-only reuse."""
    import base64
    from pathlib import PurePosixPath
    from biopipe_sdk.icons import IMAGE_TYPES
    for descriptor in descriptors:
        module = descriptor["entry_point"].split(":")[0].replace(".", "/")
        entry = module + ".py" if module + ".py" in entries else module + "/__init__.py"
        if entry not in entries:
            raise ValueError(f'Missing implementation in wheel: {entry}')
        verify_declaration(descriptor)
        top = module.split('/')[0]
        if module.startswith(('src/task/step/steps/', 'src/reader/readers/')):
            names = [n for n in entries if n.endswith('.py') and n.startswith(('src/task/step/steps/', 'src/reader/readers/'))]
        else:
            names = [n for n in entries if n.endswith('.py') and (n.startswith(top + '/') or n == top + '.py')]
        digest = hashlib.sha256()
        for name in sorted(names):
            digest.update(name.encode() + b'\0')
            digest.update(entries[name].decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8'))
        if digest.hexdigest() != descriptor['code_sha']:
            raise ValueError(f'Wheel implementation code hash mismatch: {descriptor["id"]}; rebuild the package')
        classname = descriptor['entry_point'].split(':')[1]
        cls = next(n for n in ast.parse(entries[entry].decode('utf-8')).body
                   if isinstance(n, ast.ClassDef) and n.name == classname)
        relative = 'parameters.json' if entry.endswith('/__init__.py') else PurePosixPath(entry).stem + '.parameters.json'
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if any(isinstance(t, ast.Name) and t.id == 'parameters_file' for t in targets):
                relative = ast.literal_eval(node.value)
        if not isinstance(relative, str) or ':' in relative or PurePosixPath(relative.replace('\\', '/')).is_absolute() or '..' in PurePosixPath(relative.replace('\\', '/')).parts:
            raise ValueError('parameters_file must be a contained relative JSON path')
        parameter = str(PurePosixPath(entry).parent / relative.replace('\\', '/'))
        if parameter not in entries:
            raise ValueError(f'Missing parameter JSON in wheel: {parameter}. Include it in setuptools package-data.')
        if json.loads(entries[parameter]) != descriptor['parameters_schema']:
            raise ValueError(f'Parameters changed while building wheel: {parameter}; rebuild the package')
        if not descriptor.get("icon_image"):
            continue
        asset = str(PurePosixPath(entry).parent / descriptor["icon"].replace("\\", "/"))
        if asset not in entries:
            raise ValueError(f"Missing icon in wheel: {asset}. Include it in setuptools package-data.")
        uri = f"data:{IMAGE_TYPES[PurePosixPath(asset).suffix.lower()]};base64," + base64.b64encode(entries[asset]).decode("ascii")
        if uri != descriptor["icon_image"]:
            raise ValueError(f"Icon changed while building wheel: {asset}; rebuild the package")
