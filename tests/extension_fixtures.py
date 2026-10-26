"""Explicitly migrate historical fixture declarations before v3 installation.

These helpers are test-only. The production loader never accepts class-field
declarations. Keeping numerical fixture bodies unchanged makes lifecycle and
resource regressions comparable to the protocol-v2 baseline.
"""
import ast
import json
from pathlib import Path
from copy import deepcopy


def descriptor(attributes, classname, kind, module='fixture'):
    reader = kind == 'reader'
    resources = {'memory_modes': ['full'], 'supports_cuda': attributes.get('supports_cuda', False)}
    if attributes.get('supports_streaming'):
        resources.update(memory_modes=['full', 'stream'], stream_protocol=attributes.get('stream_protocol'),
                         stream_buffer_multiplier=attributes.get('stream_buffer_multiplier', 4),
                         stream_fixed_bytes=attributes.get('stream_fixed_bytes', 0))
    if attributes.get('supports_disk_read'):
        resources.update(memory_modes=['full', 'disk'], disk_protocol=attributes.get('disk_protocol'))
    d = {'protocol_version': 3, 'id': attributes.get('name', classname), 'version': attributes.get('version', '1.0.0'),
         'kind': kind, 'entry_point': module + ':' + classname, 'title': attributes.get('title', attributes.get('name', classname)),
         'parameters_schema': deepcopy(attributes.get('parameters_schema', {'type': 'object'})),
         'contracts': {'version': 1, 'inputs': attributes.get('input_contracts', []), 'output': attributes['output_contract']},
         'resources': resources}
    for k in ('category', 'icon', 'description', 'dependencies', 'dependency_imports', 'preview', 'title_aliases', 'title_parameter'):
        if attributes.get(k) is not None:
            d[k] = attributes[k]
    d.setdefault('category', 'Plugins')
    if reader:
        for k in ('extensions', 'requires_siblings', 'excludes_siblings', 'handles_compression', 'file_input'):
            if k in attributes:
                d[k] = attributes[k]
    else:
        d.update(inputs_arity=attributes.get('inputs_arity', 0), outputs=attributes.get('outputs', []), output_parameter=attributes.get('output_parameter'))
    return d


def write_extension(path, text, **kwargs):
    """Convert old fixture source statically and write its parameter sidecars."""
    from biopipe.migrate import convert_source_parts
    from biopipe_sdk.declarations import DECLARATION_ATTRIBUTES
    from src.core.contracts import port, param, reader_contract, MISSING
    records = []
    namespace = {'port': port, 'param': param, 'reader_contract': reader_contract, 'MISSING': MISSING}
    for cls in (n for n in ast.parse(text).body if isinstance(n, ast.ClassDef)):
        attributes = {}
        for node in cls.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for t in targets:
                if isinstance(t, ast.Name) and t.id in DECLARATION_ATTRIBUTES:
                    # Only fixture metadata expressions; execution bodies and top-level code never run.
                    attributes[t.id] = eval(compile(ast.Expression(node.value), '<fixture metadata>', 'eval'), {'__builtins__': {}}, namespace)
        if attributes:
            kind = 'reader' if any(ast.unparse(b).endswith('Reader') for b in cls.bases) else 'operator'
            records.append(descriptor(attributes, cls.name, kind, Path(path).stem))
    path = Path(path)
    if records:
        text, files = convert_source_parts(text, records)
        for filename, schema in files.items():
            (path.parent / filename).write_text(json.dumps(schema), encoding='utf-8')
    path.write_text(text, encoding='utf-8')
    return path


def bound_fixture(cls, kind='operator'):
    from biopipe_sdk.declarations import DECLARATION_ATTRIBUTES, bind_class, declaration_hash
    attributes = {k: deepcopy(getattr(cls, k)) for k in DECLARATION_ATTRIBUTES if hasattr(cls, k)}
    d = descriptor(attributes, cls.__name__, kind, cls.__module__)
    d['code_sha'] = '0' * 64
    d['declaration_sha'] = declaration_hash(d)
    clean = type(cls.__name__, (cls,), {'__module__': cls.__module__})
    return bind_class(clean, d)
