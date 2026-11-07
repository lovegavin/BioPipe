"""Static script authoring and a managed, file-based execution adapter.

Inspection never imports the script. The runtime deliberately refuses to infer
scientific meaning or turn a full-memory program into a streaming implementation.
"""
import ast
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

LANGUAGES = {'.py': 'python', '.r': 'r', '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp'}
PREFIX = 'operon.script.'


def inspect_script(path):
    path = Path(path)
    return inspect_source(path.name, path.read_text(encoding='utf-8-sig'))


def inspect_source(filename, code):
    """Inspect editor text without executing it or staging temporary source files."""
    path = Path(filename)
    if path.name != filename or '/' in filename or '\\' in filename:
        raise ValueError('Script filename must be a basename')
    language = LANGUAGES.get(path.suffix.lower())
    if language is None:
        raise ValueError('Supported scripts: .py, .R, .c, .cpp and .cc')
    code = code.removeprefix('\ufeff')
    ports = {'inputs': {}, 'outputs': {}}
    dependencies = []
    requires_python = None
    for line in code.splitlines():
        match = re.fullmatch(r'\s*(?:#|//)\s*(input|output):\s+([A-Za-z_][A-Za-z0-9_]*)\s+file\.([A-Za-z0-9_.-]+)\s*', line)
        if match:
            group = 'inputs' if match[1] == 'input' else 'outputs'
            if match[2] in ports[group]:
                raise ValueError(f'Duplicate {match[1]} port: {match[2]}')
            ports[group][match[2]] = {'kind': 'file', 'format': match[3]}
    if language == 'python':
        ast.parse(code, filename=path.name)
        # PEP 723 metadata is data, not an executable provider.
        match = re.search(r'^# /// script\s*\n(.*?)^# ///\s*$', code, re.M | re.S)
        if match:
            import tomllib
            data = tomllib.loads('\n'.join(line[2:] if line.startswith('# ') else line[1:]
                                          for line in match[1].splitlines()))
            dependencies = data.get('dependencies', [])
            requires_python = data.get('requires-python')
    snapshot = {'language': language, 'code': code, 'filename': path.name,
                **ports, 'parameters_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                'dependencies': dependencies, 'code_sha': hashlib.sha256(code.encode()).hexdigest()}
    if requires_python:
        snapshot['requires_python'] = requires_python
    return validate_script(snapshot)


def validate_script(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) - {'language', 'code', 'filename', 'inputs', 'outputs', 'parameters_schema', 'dependencies', 'code_sha', 'requires_python'}:
        raise ValueError('Invalid script snapshot fields')
    value = deepcopy(snapshot)
    if value.get('language') not in LANGUAGES.values() or not isinstance(value.get('code'), str):
        raise ValueError('Script requires supported language and source code')
    filename = value.get('filename', 'script.py')
    if not isinstance(filename, str) or Path(filename).name != filename or '/' in filename or '\\' in filename:
        raise ValueError('Script filename must be a basename')
    if LANGUAGES.get(Path(filename).suffix.lower()) != value['language']:
        raise ValueError('Script filename extension must match the declared language')
    value['filename'] = filename
    digest = hashlib.sha256(value['code'].encode()).hexdigest()
    if value.get('code_sha', digest) != digest:
        raise ValueError('Script source hash does not match frozen snapshot')
    value['code_sha'] = digest
    for field in ('inputs', 'outputs'):
        if not isinstance(value.get(field), dict):
            raise ValueError(f'Script {field} must declare named file ports')
        for name, contract in value[field].items():
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) or not isinstance(contract, dict) or set(contract) != {'kind', 'format'} or contract['kind'] != 'file' or not isinstance(contract['format'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', contract['format']):
                raise ValueError('Script ports require a safe name and explicit file format')
    from operon_sdk.dependencies import requirements
    value['dependencies'] = requirements(value.get('dependencies', []))
    if value.get('requires_python') is not None:
        from packaging.specifiers import SpecifierSet
        SpecifierSet(value['requires_python'])
    from operon_sdk.protocol import validate_schema
    value.setdefault('parameters_schema', {'type': 'object', 'properties': {}, 'additionalProperties': False})
    validate_schema(value['parameters_schema'])
    if value['language'] == 'python':
        ast.parse(value['code'], filename=filename)
    return value


def parameter_candidates(code):
    """Conservative Python literals; never infer ranges or algorithm semantics."""
    tree = ast.parse(code)
    candidates = []
    writes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            writes[node.id] = writes.get(node.id, 0) + 1
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        if name.startswith('_') or writes[name] != 1:
            continue
        try:
            default = ast.literal_eval(node.value)
            json.dumps(default, allow_nan=False)
        except (ValueError, TypeError):
            continue
        if type(default) not in (bool, int, float, str, type(None)):
            continue
        kind = {bool: 'boolean', int: 'integer', float: 'number', str: 'string', type(None): 'null'}[type(default)]
        candidates.append({'name': name, 'line': node.lineno, 'schema': {'type': kind, 'default': default}})
    return candidates


def extract_parameters(snapshot, names):
    """Return source+schema together; caller saves one undoable transaction."""
    value = validate_script(snapshot)
    if value['language'] != 'python':
        raise ValueError('Automatic parameter binding currently supports Python; edit other language templates explicitly')
    available = {item['name']: item for item in parameter_candidates(value['code'])}
    if not names or len(set(names)) != len(names) or set(names) - set(available):
        raise ValueError('Select unique supported parameter candidates')
    tree = ast.parse(value['code'])
    if any(isinstance(node, ast.Name) and node.id.startswith('__operon_') for node in ast.walk(tree)):
        raise ValueError('Reserved parameter binding names already occur in source')
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            node.value = ast.Subscript(value=ast.Name(id='__operon_values', ctx=ast.Load()),
                                       slice=ast.Constant(value=node.targets[0].id), ctx=ast.Load())
    bootstrap = ast.parse('import json as __operon_json\nimport os as __operon_os\nfrom pathlib import Path as __operon_Path\n__operon_values = __operon_json.loads(__operon_Path(__operon_os.environ["OPERON_PARAMETERS_FILE"]).read_text(encoding="utf-8"))\n').body
    offset = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str) else 0
    while offset < len(tree.body) and isinstance(tree.body[offset], ast.ImportFrom) and tree.body[offset].module == '__future__':
        offset += 1
    tree.body[offset:offset] = bootstrap
    header = []
    for kind in ('input', 'output'):
        header.extend(f"# {kind}: {name} file.{contract['format']}" for name, contract in value[kind + 's'].items())
    if value['dependencies'] or value.get('requires_python'):
        header.extend(['# /// script', '# dependencies = ' + json.dumps(value['dependencies'])])
        if value.get('requires_python'):
            header.append('# requires-python = ' + json.dumps(value['requires_python']))
        header.append('# ///')
    value['code'] = '\n'.join(header) + '\n' + ast.unparse(ast.fix_missing_locations(tree)) + '\n'
    value['code_sha'] = hashlib.sha256(value['code'].encode()).hexdigest()
    schema = deepcopy(value['parameters_schema'])
    schema.setdefault('properties', {}).update({name: available[name]['schema'] for name in names})
    value['parameters_schema'] = schema
    return {'script': validate_script(value), 'values': {name: available[name]['schema']['default'] for name in names},
            'bindings': {name: {'kind': 'environment-json', 'key': name} for name in names}}


def execute_script(snapshot, values, inputs, output_dir, *, cancel=None, timeout=3600, python=None, rscript=None, compiler=None):
    """Run a frozen script with file-backed logs and process-tree ownership."""
    snapshot = validate_script(snapshot)
    from operon_sdk.protocol import validate_parameters
    values = validate_parameters(snapshot['parameters_schema'], values)
    if set(inputs) != set(snapshot['inputs']):
        raise ValueError('Script input files must match declared ports')
    if not snapshot['outputs']:
        raise ValueError('Script requires at least one declared output')
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Script timeout must be positive')
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    script = directory / snapshot['filename']
    script.write_text(snapshot['code'], encoding='utf-8')
    parameters = directory / 'parameters.json'
    parameters.write_text(json.dumps(values, allow_nan=False), encoding='utf-8')
    paths = {name: directory / (name + '.' + contract['format']) for name, contract in snapshot['outputs'].items()}
    reserved = {script.name.casefold(), 'parameters.json', 'console.log', 'build.log', 'program.exe', 'program'}
    if any(path.name.casefold() in reserved for path in paths.values()):
        raise ValueError('Output filename collides with a runtime control file')
    env = os.environ.copy()
    env['OPERON_PARAMETERS_FILE'] = str(parameters)
    scratch = directory / 'tmp'
    scratch.mkdir()
    env.update(TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
    from .processes import owned_process

    def command(argv, log):
        with log.open('wb') as output, owned_process(argv, cwd=directory, env=env, stdout=output, stderr=output) as process:
            start = time.monotonic()
            try:
                while process.poll() is None:
                    if cancel and cancel():
                        raise RuntimeError('Script cancelled')
                    if time.monotonic() - start > timeout:
                        raise TimeoutError('Script execution timed out')
                    time.sleep(.05)
                if process.returncode:
                    # Keep the full native log on disk and surface a bounded tail
                    # through the ordinary job log, including CLI/remote callers.
                    with log.open('rb') as retained:
                        retained.seek(max(0, log.stat().st_size - 8192))
                        tail = retained.read(8192).decode('utf-8', errors='replace').strip()
                    raise RuntimeError(f'Script process exited {process.returncode}; log: {log}\n{tail}')
            finally:
                pass  # owned_process closes the entire process tree on exit

    language = snapshot['language']
    if language == 'python':
        executable = python or sys.executable
        if Path(executable).resolve() == Path(sys.executable).resolve():
            readiness = inspect_script_environment(snapshot)
            if readiness['status'] != 'passed':
                raise ValueError(readiness['error'])
            # The parent may be an isolated dependency worker. -I alone would
            # discard its selected target directories. Freeze its absolute
            # import paths, without adding CWD, script folders or PYTHONPATH.
            import_paths = list(dict.fromkeys(str(Path(p).resolve()) for p in sys.path
                                      if p and Path(p).is_absolute() and Path(p).resolve() != Path.cwd().resolve()))
            environment = directory / 'python-paths.json'
            environment.write_text(json.dumps(import_paths), encoding='utf-8')
            bootstrap = ('import json,sys,runpy; '
                         'paths=json.load(open(sys.argv[1],encoding="utf-8")); '
                         'sys.path[:]=paths; sys.argv=sys.argv[2:]; '
                         'runpy.run_path(sys.argv[0],run_name="__main__")')
            argv = [executable, '-I', '-S', '-c', bootstrap, str(environment), str(script)]
        else:
            # An explicitly supplied interpreter owns its own dependencies;
            # do not contaminate it with packages from the Operon host.
            argv = [executable, '-I', str(script)]
    elif language == 'r':
        executable = rscript or shutil.which('Rscript')
        if not executable:
            raise ValueError('The selected environment has no Rscript')
        argv = [executable, '--vanilla', str(script)]
    else:
        executable = compiler or shutil.which('c++' if language == 'cpp' else 'cc')
        if not executable:
            raise ValueError('The selected environment has no C/C++ compiler')
        binary = directory / ('program.exe' if os.name == 'nt' else 'program')
        command([executable, str(script), '-o', str(binary)], directory / 'build.log')
        argv = [str(binary)]
    for name, file in inputs.items():
        path = Path(file).resolve()
        if not path.is_file():
            raise ValueError(f'Missing input file {name}: {path}')
        argv.extend(['--in-' + name, str(path)])
    for name, path in paths.items():
        argv.extend(['--out-' + name, str(path)])
    command(argv, directory / 'console.log')
    for name, path in paths.items():
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise ValueError(f'Script did not create declared output {name}')
    return {'files': {name: str(path) for name, path in paths.items()}, 'directory': str(directory),
            'code_sha': snapshot['code_sha'], 'parameters': values}


def _script_formats(snapshot):
    """The script bridge exchanges declared files, never implicit Forms."""
    return {'inputs': [{'logical_type': 'file_artifact', 'representations': ['file_artifact']}
                       for _ in snapshot['inputs']],
            'outputs': [{'logical_type': 'file_artifact', 'representations': ['file_artifact']}
                        for _ in snapshot['outputs']]}


def prepare_script_graph(graph, catalog):
    """Transient projection only. Never replace the saved script graph."""
    from src.web.models import Graph
    result = Graph.model_validate(graph) if isinstance(graph, dict) else graph.model_copy(deep=True)
    catalog = deepcopy(catalog)
    for node in result.nodes:
        if node.kind != 'script':
            continue
        script = validate_script(node.script)
        if len(script['outputs']) != 1:
            raise ValueError('Graph script nodes currently require one file output; split multiple outputs explicitly')
        identity = hashlib.sha256(json.dumps(script, sort_keys=True).encode()).hexdigest()
        name = PREFIX + identity[:24]
        # Only the explicitly declared file interface is admitted. No Form ->
        # file conversion or semantic type is invented here.
        output = next(iter(script['outputs'].values()))
        descriptor = {'id': name, 'title': node.title or script['filename'], 'description': 'Workflow-local script',
                      'protocol_revision': '3.7', 'data_formats': _script_formats(script),
                      'runtime_defaults': {},
                      'inputs_arity': len(script['inputs']), 'outputs': [], 'output_parameter': 'output',
                      'parameters_schema': {'type': 'object', 'properties': {'script': {'type': 'object'}, 'values': script['parameters_schema']}, 'required': ['script', 'values'], 'additionalProperties': False},
                      'contracts': {'version': 1, 'inputs': [_file_contract(item['format']) for item in script['inputs'].values()],
                                    'output': {'mode': 'declare', 'schema': {**_file_contract(output['format']), 'labels': {}, 'axis_info': {}}}},
                      'resources': {'memory_modes': ['full']}, 'dependencies': script['dependencies'],
                      'dependency_imports': [], 'supported_systems': ['windows', 'linux', 'darwin'],
                      'script': script}
        if not any(item['id'] == name for item in catalog['operators']):
            catalog['operators'].append(descriptor)
        node.kind, node.operator = 'operator', name
        node.params = {'script': script, 'values': deepcopy(node.params), 'output': node.id}
        node.script = None
    return result, catalog


def script_step_class(name, snapshot):
    """Create an engine Step lazily, after a job has selected its environment."""
    from src.task.step.base import Step
    snapshot = validate_script(snapshot)
    identity = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    if name != PREFIX + identity[:24]:
        raise ValueError('Script operator identity does not match its frozen source and interface')
    if len(snapshot['outputs']) != 1:
        raise ValueError('Script Step requires exactly one file output')
    output = next(iter(snapshot['outputs'].values()))

    class ScriptStep(Step):
        inputs_arity = len(snapshot['inputs'])
        output_parameter = 'output'
        outputs = []
        parameters_schema = {'type': 'object', 'properties': {'script': {'type': 'object'}, 'values': snapshot['parameters_schema']}, 'required': ['script', 'values'], 'additionalProperties': False}
        input_contracts = [_file_contract(item['format']) for item in snapshot['inputs'].values()]
        output_contract = {'mode': 'declare', 'schema': {**_file_contract(output['format']), 'labels': {}, 'axis_info': {}}}
        dependencies = snapshot['dependencies']

        def run(self, ctx, inputs):
            self.result = run_script_step(ctx.step_params['script'], ctx, inputs,
                                          ctx.step_params['values'], ctx.step_params.get('output', name))

        def export(self, ctx):
            return self.result
    ScriptStep.name = name
    ScriptStep._declaration = {
        'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': _script_formats(snapshot),
        'id': name, 'version': '1.0.0', 'kind': 'operator',
        'entry_point': __name__ + ':ScriptStep', 'title': snapshot['filename'],
        'description': 'Workflow-local file script', 'category': 'data',
        'parameters_schema': ScriptStep.parameters_schema,
        'contracts': {'version': 1, 'inputs': ScriptStep.input_contracts, 'output': ScriptStep.output_contract},
        'inputs_arity': ScriptStep.inputs_arity, 'outputs': [], 'output_parameter': 'output',
        'resources': {'memory_modes': ['full'], 'supports_cuda': False},
        'dependencies': snapshot['dependencies'], 'dependency_imports': [],
        'code_sha': snapshot['code_sha'], 'declaration_sha': identity,
    }
    return ScriptStep


def run_script_step(snapshot, ctx, inputs, values, output):
    """Shared native Step bridge for local scripts and promoted v3 providers."""
    from src.core import FileArtifact
    snapshot = validate_script(snapshot)
    if len(snapshot['outputs']) != 1 or len(inputs) != len(snapshot['inputs']):
        raise ValueError('Script Step requires its declared inputs and exactly one output')
    files = {}
    for port, artifact in zip(snapshot['inputs'], inputs):
        if not isinstance(artifact, FileArtifact) or len(artifact.files) != 1:
            raise ValueError('Script inputs require a single-file artifact; use an explicit converter')
        artifact.validate()
        files[port] = next(iter(artifact.files.values()))
    result = execute_script(snapshot, values, files, ctx.out_dir / 'scripts' / uuid.uuid4().hex,
                            cancel=lambda: (ctx.task_dir / 'cancel.requested').exists())
    for artifact in inputs:
        artifact.validate()
    format = next(iter(snapshot['outputs'].values()))['format']
    ctx[output] = FileArtifact(format, result['files'])
    return result


def export_script_package(snapshot, directory, *, operator_id, title, category='data', version='0.1.0'):
    """Create a static v3 source project; installing it is a separate action.

    The frozen script is literal data in the provider source, so its identity
    includes every executable byte. Editable defaults stay in parameters.json.
    """
    import pprint
    from packaging.version import Version
    snapshot = validate_script(snapshot)
    if len(snapshot['outputs']) != 1:
        raise ValueError('A promoted script requires exactly one file output')
    if not isinstance(operator_id, str) or not re.fullmatch(r'[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+', operator_id) or operator_id.startswith(PREFIX):
        raise ValueError('Choose a namespaced operator ID such as lab.my_filter')
    if not isinstance(title, str) or not title.strip() or not isinstance(category, str) or not category.strip() or '\0' in category:
        raise ValueError('A nonempty title and a valid category are required')
    version = str(Version(version))
    schema = deepcopy(snapshot['parameters_schema'])
    if set(schema.get('properties', {})) & {'output', '_input_names'}:
        raise ValueError('Parameter name is reserved by the engine')
    directory = Path(directory).resolve()
    if directory.exists() and (not directory.is_dir() or any(directory.iterdir())):
        raise ValueError('Choose a new or empty plugin directory')
    module = 'operon_user_' + operator_id.replace('.', '_')
    package = module.replace('_', '-')
    output = next(iter(snapshot['outputs'].values()))
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'data_formats': _script_formats(snapshot),
                  'id': operator_id, 'version': version, 'kind': 'operator',
                  'title': title.strip(), 'description': 'User-authored file script', 'category': category,
                  'contracts': {'version': 1, 'inputs': [_file_contract(p['format']) for p in snapshot['inputs'].values()],
                                'output': {'mode': 'declare', 'schema': {**_file_contract(output['format']), 'labels': {}, 'axis_info': {}}}},
                  'resources': {'memory_modes': ['full'], 'supports_cuda': False},
                  'inputs_arity': len(snapshot['inputs']), 'outputs': [], 'output_parameter': 'output',
                  'dependencies': snapshot['dependencies']}
    # Schema belongs to the v3 JSON declaration, not the immutable implementation.
    frozen = deepcopy(snapshot)
    frozen.pop('parameters_schema')
    source = ('from operon_sdk import Step\n'
              'from operon.script_operators import run_script_step\n\n'
              'SCRIPT = ' + pprint.pformat(frozen, width=100, sort_dicts=False) + '\n\n'
              'class ScriptStep(Step):\n'
              '    parameters_file = "parameters.json"\n'
              '    definition = ' + pprint.pformat(definition, width=100, sort_dicts=False).replace('\n', '\n    ') + '\n\n'
              '    def run(self, ctx, inputs):\n'
              '        snapshot = dict(SCRIPT, parameters_schema=self.parameters_schema)\n'
              '        values = {k: v for k, v in ctx.step_params.items() if k not in {"output", "_input_names"}}\n'
              '        self.result = run_script_step(snapshot, ctx, inputs, values, ctx.step_params.get("output", self.name))\n\n'
              '    def export(self, ctx):\n'
              '        return self.result\n')
    folder = directory / module
    folder.mkdir(parents=True)
    (folder / '__init__.py').write_text(source, encoding='utf-8')
    (folder / 'parameters.json').write_text(json.dumps(schema, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (directory / 'pyproject.toml').write_text(
        '[build-system]\nrequires = ["setuptools>=69"]\nbuild-backend = "setuptools.build_meta"\n'
        f'[project]\nname = "{package}"\nversion = "{version}"\nrequires-python = ">=3.11"\n'
        'dependencies = ["operon-studio>=3.0.0,<4"]\n'
        f'[project.entry-points."operon.operators"]\n{module} = "{module}:ScriptStep"\n'
        f'[tool.setuptools.packages.find]\ninclude = ["{module}*"]\n'
        f'[tool.setuptools.package-data]\n"{module}" = ["*.json", "*.md"]\n', encoding='utf-8')
    ports = '\n'.join(f'- {kind}: `{name}` (`{p["format"]}`)' for kind in ('inputs', 'outputs') for name, p in snapshot[kind].items())
    (folder / '__init__.md').write_text(
        f'# {title.strip()}\n\n## Purpose\n\nUser-authored {snapshot["language"]} script `{operator_id}`. '
        'Review the scientific meaning before reuse.\n\n## Inputs and outputs\n\n' + ports +
        '\n\n## Parameters\n\nEdit the independent `parameters.json` schema and defaults. '
        'Saved workflows retain their own frozen values.\n\n## Execution\n\n'
        'The source runs in a managed subprocess with named file arguments and a parameter JSON. '
        'It does not run during registration.\n\n## Limitations\n\n'
        'One file output. No inferred streaming or scientific conversions. '
        'External tools and declared dependencies must be ready in the selected environment.\n', encoding='utf-8')
    (directory / 'README.md').write_text(
        f'# {title.strip()}\n\nRun `operon plugin check .`, then `operon plugin build .`. '
        'Install the resulting wheel through Add operators. This source project does not install or execute itself.\n', encoding='utf-8')
    return {'path': str(directory), 'module': module, 'id': operator_id, 'package': package,
            'version': version, 'parameters': str(folder / 'parameters.json')}


def _file_contract(format):
    return {'version': 1, 'kind': 'file', 'numeric': False, 'dims': [], 'ndim': 0,
            'labels': [], 'parallel': [], 'info': {'representation': {'type': 'string', 'const': format}}}


def inspect_script_environment(snapshot):
    """Read-only readiness for the current selected worker environment."""
    from importlib.metadata import PackageNotFoundError, version
    from packaging.requirements import Requirement
    value = validate_script(snapshot)
    errors = []
    language = value['language']
    if language == 'python' and value.get('requires_python'):
        from packaging.specifiers import SpecifierSet
        if '.'.join(map(str, sys.version_info[:3])) not in SpecifierSet(value['requires_python']):
            errors.append('Python version does not satisfy ' + value['requires_python'])
    tool = None if language == 'python' else 'Rscript' if language == 'r' else 'c++' if language == 'cpp' else 'cc'
    if tool and not shutil.which(tool):
        errors.append(f'Missing executable: {tool}')
    if language != 'python' and value['dependencies']:
        errors.append('Non-Python dependency declarations need an explicitly prepared tool environment')
    for text in value['dependencies'] if language == 'python' else []:
        requirement = Requirement(text)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        if requirement.url or requirement.extras:
            errors.append(f'An explicit frozen environment is required for {text}')
            continue
        try:
            installed = version(requirement.name)
            if requirement.specifier and installed not in requirement.specifier:
                errors.append(f'{requirement.name} {installed} does not satisfy {requirement.specifier}')
        except PackageNotFoundError:
            errors.append(f'Missing package: {requirement.name}')
    return {'status': 'failed' if errors else 'passed', 'error': '; '.join(errors) if errors else None,
            'language': language, 'python': sys.executable if language == 'python' else None,
            'tool': shutil.which(tool) if tool else None}
