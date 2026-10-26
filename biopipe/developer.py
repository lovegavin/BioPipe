"""Plugin scaffolding, source validation and wheel builds."""
import importlib
from contextlib import redirect_stdout
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
import zipfile

from biopipe.plugins import run_process
from biopipe import __version__
from biopipe_sdk.protocol import describe_operator, describe_reader, validate_extension, PROTOCOL_VERSION


def scaffold(path, template="operator"):
    path = Path(path).resolve()
    if path.exists() and any(path.iterdir()):
        raise ValueError("Choose a new or empty plugin directory")
    module = re.sub(r"[^a-z0-9_]", "_", path.name.lower())
    if not module or module[0].isdigit():
        module = "plugin_" + module
    package = module.replace("_", "-")
    folder = path / module
    folder.mkdir(parents=True, exist_ok=True)
    reader = template == 'reader'
    cls, group = ('ArrayReader', 'readers') if reader else ('Scale', 'operators')
    (path / 'pyproject.toml').write_text(f'''[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"
[project]
name = "{package}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["biopipe-studio>={__version__},<1"]
[project.entry-points."biopipe.{group}"]
{module} = "{module}:{cls}"
[tool.setuptools.packages.find]
include = ["{module}*"]
[tool.setuptools.package-data]
"{module}" = ["*.json", "*.svg", "*.png"]
''', encoding='utf-8')
    source = '''"""Numerical implementation. Edit parameter defaults in parameters.json."""
import numpy as np
from biopipe_sdk import Operator, Form, project_metadata

class Scale(Operator):
    def compute(self, inputs, params, context):
        form = inputs[0]
        info, axes = project_metadata(form, derived=True)
        info.update(representation='scaled', missing_code=float('nan'))
        data = form.data.astype(float, copy=True)
        missing = form.info.get('missing_code')
        if missing is not None:
            data[data == missing] = np.nan
        data *= params['factor']
        return Form(data=data, dims=list(form.dims),
                    labels={d: dict(v) for d, v in form.labels.items()}, info=info, axis_info=axes)

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        cells = inputs[0].data.size
        return cells, cells * 8 + sum(len(v) for v in inputs[0].labels.values()) * 96
'''
    if reader:
        source = '''import numpy as np
from biopipe_sdk import Reader, Form

class ArrayReader(Reader):
    def read(self, path, dims, labels, **args):
        data = np.load(path, allow_pickle=False)
        mapping = {dim: {str(i): i for i in range(data.shape[axis])} for axis, dim in enumerate(dims)}
        return Form(data=data, dims=dims, labels=mapping, info={'missing_code': float('nan')})
'''
    from src.core.contracts import port, reader_contract
    declaration = dict(protocol_version=3, id=f'example.{module}', version='0.1.0',
                       kind='reader' if reader else 'operator', entry_point=f'{module}:{cls}',
                       title='Array reader' if reader else 'Scale matrix', category='data',
                       parameters_schema={'type': 'object', 'additionalProperties': False,
                                          'properties': {} if reader else {'factor': {'type': 'number', 'default': 2.0, 'title': 'Scale factor'}}},
                       contracts={'version': 1, 'inputs': [] if reader else [port(ndim=2)],
                                  'output': reader_contract() if reader else {'mode': 'transform', 'representation': 'scaled'}},
                       resources={'memory_modes': ['full'], 'supports_cuda': False},
                       **({'extensions': ['.npy']} if reader else {'inputs_arity': 1, 'output_parameter': 'output'}))
    import pprint
    parameters = declaration.pop('parameters_schema')
    declaration.pop('entry_point')
    definition = '    parameters_file = "parameters.json"\n    definition = ' + pprint.pformat(declaration, width=100, sort_dicts=False).replace('\n', '\n    ') + '\n'
    source = source.replace(f'class {cls}(' + ('Reader' if reader else 'Operator') + '):\n',
                            f'class {cls}(' + ('Reader' if reader else 'Operator') + '):\n' + definition)
    (folder / '__init__.py').write_text(source, encoding='utf-8')
    (folder / 'parameters.json').write_text(json.dumps(parameters, indent=2)+'\n', encoding='utf-8')
    (path / 'README.md').write_text(f'''# {package}

BioPipe SDK v3. Edit `{module}/parameters.json` for parameters; keep the operator definition with its implementation.

Run `biopipe plugin check .`, `biopipe plugin test .`, then `biopipe plugin build .`.
Install the wheel or put the project in the operator inbox and refresh.
''', encoding='utf-8')
    (path / 'tests').mkdir(exist_ok=True)
    test = f'''import numpy as np
from {module} import {cls}
from biopipe_sdk.declarations import bind_class, for_class

def test_declaration():
    bound = bind_class({cls}, for_class({cls}))
    assert bound.parameters_schema['type'] == 'object'
'''
    if not reader:
        test += '''
def test_scale():
    from biopipe_sdk import Form
    from biopipe_sdk.testing import run_operator
    data = np.arange(6, dtype=float).reshape(2, 3)
    form = Form(data, ['sample', 'feature'], {'sample': {'a': 0, 'b': 1}, 'feature': {'x': 0, 'y': 1, 'z': 2}}, {'missing_code': float('nan')})
    output = run_operator(Scale, [form], {'factor': 3})
    np.testing.assert_allclose(output.data, data * 3)
    np.testing.assert_allclose(form.data, data)
'''
    (path / 'tests/test_plugin.py').write_text(test, encoding='utf-8')
    return {'path': str(path), 'module': module, 'template': template}


def check_source(path):
    """Compile external declarations and inspect code without importing it."""
    from biopipe_sdk.declarations import compile_declaration, source_declarations
    from biopipe_sdk.drift import check_source as check_drift
    from packaging.utils import canonicalize_name
    from biopipe_sdk.protocol import PackageDescriptor
    path = Path(path).resolve()
    root = path / 'src' if (path / 'src').is_dir() else path
    project = tomllib.loads((path / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    descriptors = []
    for group, kind in (('biopipe.operators', 'operator'), ('biopipe.readers', 'reader')):
        for entry in project.get('entry-points', {}).get(group, {}).values():
            module = entry.split(':')[0].replace('.', '/')
            source = root / (module + '.py')
            if not source.is_file():
                source = root / module / '__init__.py'
            declared = {d['entry_point']: d for d in source_declarations(source, entry.split(':')[0])}
            if entry not in declared:
                raise ValueError(f'{entry}: define the protocol and a separate parameter JSON (v3)')
            d = compile_declaration(declared[entry], root)
            if d['kind'] != kind:
                raise ValueError('Entry point kind differs from declaration')
            errors, warnings = check_drift(source.read_text(encoding='utf-8'), d)
            if errors:
                raise ValueError(f'{entry}: ' + '; '.join(errors))
            from biopipe.packages import owns_builtin_id
            if '.' not in d['id'] and not owns_builtin_id(canonicalize_name(project['name']), d['id']):
                raise ValueError('Use a namespaced ID such as lab.scale')
            descriptors.append(d)
    if not descriptors:
        raise ValueError('No BioPipe entry points declared')
    value = {'protocol_version': PROTOCOL_VERSION, 'name': canonicalize_name(project['name']),
             'version': project['version'], 'origin': 'wheel', 'dependencies': project.get('dependencies', []), 'descriptors': descriptors}
    PackageDescriptor.model_validate(value)
    return value


def build(path):
    path = Path(path).resolve()
    previous = {p: p.stat().st_mtime_ns for p in (path / "dist").glob("*.whl")}
    manifest = json.loads(run_process([sys.executable, "-m", "biopipe.developer", "check", path]))
    run_process([sys.executable, "-m", "build", "--wheel", "--no-isolation", path], timeout=180)
    wheels = [p for p in sorted((path / "dist").glob("*.whl")) if p.stat().st_mtime_ns != previous.get(p)]
    for wheel in wheels:
        embed_manifest(wheel, manifest)
    (path / "biopipe-plugin.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"wheels": list(map(str, wheels)), "manifest": str(path / "biopipe-plugin.json")}


def embed_manifest(wheel, manifest):
    """Publish metadata inside the wheel, updating its standard RECORD hashes."""
    with zipfile.ZipFile(wheel) as archive:
        entries = {item.filename: (item, archive.read(item)) for item in archive.infolist()}
    from biopipe_sdk.declarations import verify_archive
    verify_archive({name: content for name, (_, content) in entries.items()}, manifest['descriptors'])
    record = next(name for name in entries if name.endswith(".dist-info/RECORD"))
    target = record.rsplit("/", 1)[0] + "/biopipe.json"
    data = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    rows = [row for row in csv.reader(io.StringIO(entries[record][1].decode("utf-8"))) if row[0] not in (target, record)]
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
    rows.extend([[target, "sha256=" + digest, str(len(data))], [record, "", ""]])
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    temporary = wheel.with_suffix(".whl.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, (info, content) in entries.items():
            if name not in (record, target):
                archive.writestr(info, content)
        archive.writestr(target, data)
        archive.writestr(record, output.getvalue().encode("utf-8"))
    temporary.replace(wheel)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "check":
        with redirect_stdout(sys.stderr):
            result = check_source(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
