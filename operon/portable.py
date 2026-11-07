"""Export independent, file-based Python script workflows with a real runtime.

Native Context/Form implementations need an explicit portable adapter and fail
closed here. A requirements file alone is never called a bundled environment.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

from .script_operators import validate_script


class PortableError(ValueError):
    code = 'portable_unsupported'


def check_portable(graph):
    from src.web.models import Graph
    graph = Graph.model_validate(graph).model_dump(mode='json')
    unsupported = []
    for node in graph['nodes']:
        if node['kind'] == 'source':
            source = node['source']
            if source.get('location') and source['location']['kind'] != 'local':
                unsupported.append(f"{node['id']}: remote input needs an explicit local export source")
            if source.get('args') or source.get('reader'):
                unsupported.append(f"{node['id']}: explicit Reader needs a portable adapter")
        elif node['kind'] != 'script':
            unsupported.append(f"{node['id']}: native/route operator needs a verified portable implementation")
        else:
            snapshot = validate_script(node['script'])
            if snapshot['language'] != 'python':
                unsupported.append(f"{node['id']}: bundled export currently supports Python scripts")
            if len(snapshot['outputs']) != 1:
                unsupported.append(f"{node['id']}: graph script export requires one output file")
    for edge in graph['edges']:
        adaptation = edge.get('adaptation') or {}
        if adaptation.get('converters'):
            unsupported.append(f"{edge['id']}: fixed converter requires a verified portable implementation")
    if unsupported:
        raise PortableError('Cannot export a complete standalone package: ' + '; '.join(unsupported))
    from .script_operators import prepare_script_graph
    # Static order and file types are verified independently of a local library.
    nodes = {node['id']: node for node in graph['nodes']}
    if len(nodes) != len(graph['nodes']):
        raise PortableError('Duplicate node IDs')
    incoming = {key: {} for key in nodes}
    for edge in graph['edges']:
        if edge['source'] not in nodes or edge['target'] not in nodes or nodes[edge['target']]['kind'] != 'script':
            raise PortableError('Invalid standalone edge')
        if edge['sourceHandle'] not in ('out', 'out-0'):
            raise PortableError('Standalone script output port does not exist')
        index = int(edge['targetHandle'].split('-')[1])
        if index in incoming[edge['target']]:
            raise PortableError('Duplicate input binding')
        incoming[edge['target']][index] = edge['source']
    pending = dict(nodes)
    done, plan = set(), []
    while pending:
        ready = [node for node in pending.values() if set(incoming[node['id']].values()) <= done]
        if not ready:
            raise PortableError('Workflow contains a cycle')
        for node in ready:
            key = node['id']
            if node['kind'] == 'script':
                names = list(node['script']['inputs'])
                if set(incoming[key]) != set(range(len(names))):
                    raise PortableError(f'{key}: connect every declared input')
                bindings = {name: incoming[key][index] for index, name in enumerate(names)}
                for port, source_id in bindings.items():
                    source_node = nodes[source_id]
                    if source_node['kind'] == 'script':
                        actual = next(iter(source_node['script']['outputs'].values()))['format']
                        required = node['script']['inputs'][port]['format']
                        if actual != required:
                            raise PortableError(f'{source_id} -> {key}: conversion requires a portable adapter')
                plan.append({'id': key, 'script': deepcopy(node['script']), 'values': deepcopy(node['params']), 'inputs': bindings})
            done.add(key)
            pending.pop(key)
    return graph, plan


def _runtime(directory, requirements):
    if directory is None:
        raise PortableError('A prepared relocatable --runtime-dir is required; dependencies are not downloaded during export')
    directory = Path(directory).resolve()
    descriptor = directory / 'portable-runtime.json'
    if not descriptor.is_file():
        raise PortableError('Runtime requires portable-runtime.json with platform, machine and python entry point')
    record = json.loads(descriptor.read_text(encoding='utf-8'))
    if record.get('format') != 'operon.portable-runtime' or record.get('schema_version') != 1:
        raise PortableError('Unsupported portable runtime manifest')
    if record.get('platform') != sys.platform or record.get('machine', '').lower() != platform.machine().lower():
        raise PortableError('Build and runtime platform must match for verification')
    path = Path(record.get('python', ''))
    if not re.fullmatch(r'[A-Za-z0-9_./\\ -]+', str(path)):
        raise PortableError('Runtime entry point contains unsupported launcher characters')
    executable = (directory / path).resolve()
    if path.is_absolute() or not executable.is_relative_to(directory) or not executable.is_file():
        raise PortableError('Runtime Python must be an existing relative file inside runtime')
    if (directory / 'pyvenv.cfg').exists():
        raise PortableError('An arbitrary venv is not relocatable; provide a prepared runtime')
    # Probe the actual interpreter, rather than trusting a manifest claim.
    probe = 'import json,sys,platform; from importlib.metadata import distributions; print(json.dumps({"platform":sys.platform,"machine":platform.machine(),"packages":{d.metadata["Name"].lower().replace("_","-"):d.version for d in distributions()}}))'
    completed = subprocess.run([str(executable), '-I', '-c', probe], capture_output=True, text=True, timeout=45, check=True)
    actual = json.loads(completed.stdout)
    if actual['platform'] != record['platform'] or actual['machine'].lower() != record['machine'].lower():
        raise PortableError('Runtime metadata does not match its interpreter')
    from packaging.requirements import Requirement
    for text in requirements:
        requirement = Requirement(text)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        version = actual['packages'].get(requirement.name.lower().replace('_', '-'))
        if requirement.extras or requirement.url or version is None or version not in requirement.specifier:
            raise PortableError(f'Runtime cannot prove locked dependency {text}')
    return directory, record


RUNNER = '''"""Independent exported analysis. Edit INPUTS and OUTPUT_DIR here."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
INPUTS = __INPUTS__
OUTPUT_DIR = ROOT / "results"

def main():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    if sys.platform != manifest["runtime"]["platform"]:
        raise SystemExit("This analysis package targets another operating system")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {key: str(Path(path) if Path(path).is_absolute() else ROOT / path) for key, path in INPUTS.items()}
    values = json.loads((ROOT / "parameters.json").read_text(encoding="utf-8"))
    for node in manifest["steps"]:
        directory = OUTPUT_DIR / node["id"]
        directory.mkdir(parents=True, exist_ok=False)
        parameter_file = directory / "parameters.json"
        parameter_file.write_text(json.dumps(values[node["id"]], allow_nan=False), encoding="utf-8")
        env = os.environ.copy()
        env["OPERON_PARAMETERS_FILE"] = str(parameter_file)
        scratch = directory / "tmp"
        scratch.mkdir()
        env.update(TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
        command = [sys.executable, "-I", str(ROOT / node["source"])]
        for port, key in node["inputs"].items():
            path = Path(paths[key])
            if not path.is_file():
                raise FileNotFoundError(path)
            command.extend(["--in-" + port, str(path)])
        output = directory / (node["output_name"] + "." + node["output_format"])
        command.extend(["--out-" + node["output_name"], str(output)])
        with (directory / "console.log").open("wb") as log:
            subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=log, check=True)
        if not output.is_file() or output.is_symlink():
            raise RuntimeError("Missing declared output: " + str(output))
        paths[node["id"]] = str(output)
    (OUTPUT_DIR / "run.json").write_text(json.dumps({"inputs": INPUTS, "outputs": paths, "parameters": values}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
'''


def export_portable(graph, output, *, runtime_dir=None):
    graph, plan = check_portable(graph)
    requirements = sorted({requirement for node in plan for requirement in node['script']['dependencies']})
    runtime, record = _runtime(runtime_dir, requirements)
    output = Path(output).resolve()
    if output == runtime or output.is_relative_to(runtime) or runtime.is_relative_to(output):
        raise PortableError('Export and runtime directories must be separate')
    if output.exists() and any(output.iterdir()):
        raise PortableError('Export directory must be empty')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'operators').mkdir()
    (output / 'converters').mkdir()
    shutil.copytree(runtime, output / 'runtime', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Verify relocation before claiming the runtime is bundled successfully.
    _runtime(output / 'runtime', requirements)
    values, steps = {}, []
    from operon_sdk.protocol import validate_parameters
    for node in plan:
        filename = 'operators/' + node['id'] + '.py'
        (output / filename).write_text(node['script']['code'], encoding='utf-8')
        name, contract = next(iter(node['script']['outputs'].items()))
        steps.append({'id': node['id'], 'source': filename, 'code_sha': node['script']['code_sha'],
                      'inputs': node['inputs'], 'output_name': name, 'output_format': contract['format']})
        values[node['id']] = validate_parameters(node['script']['parameters_schema'], node['values'])
    inputs = {node['id']: 'inputs/' + node['id'] + '/' + Path(node['source']['path']).name
              for node in graph['nodes'] if node['kind'] == 'source'}
    (output / 'parameters.json').write_text(json.dumps(values, indent=2, allow_nan=False), encoding='utf-8')
    (output / 'run.py').write_text(RUNNER.replace('__INPUTS__', repr(inputs)), encoding='utf-8')
    if os.name == 'nt':
        entry = record['python'].replace('/', '\\')
        (output / 'run.cmd').write_text('@echo off\r\n"%~dp0runtime\\' + entry + '" -I "%~dp0run.py"\r\nexit /b %errorlevel%\r\n', encoding='utf-8')
    else:
        entry = record['python']
        if any(char in entry for char in ('"', '$', '`', '\n', '\r')):
            raise PortableError('Runtime entry point cannot be safely quoted')
        (output / 'run.sh').write_text('#!/bin/sh\nROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$ROOT/runtime/' + entry + '" -I "$ROOT/run.py"\n', encoding='utf-8')
        (output / 'run.sh').chmod(0o755)
    manifest = {'format': 'operon.standalone', 'schema_version': 1, 'runtime': record, 'steps': steps,
                'converters': [], 'dependencies': requirements, 'inputs_included': False}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (output / 'README.md').write_text('# Independent analysis\n\nEdit INPUTS and OUTPUT_DIR at the top of run.py. Input data is not included.\nRun run.cmd on Windows or run.sh on Linux. No Operon or global Python is used.\nChoose a fresh output directory for each run; existing results are not overwritten.\nThe runtime directory includes its own license notices.\n', encoding='utf-8')
    return {'path': str(output), 'format': 'standalone', 'runtime_bundled': True, 'steps': len(steps), 'inputs_included': False}
