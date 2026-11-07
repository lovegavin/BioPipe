#!/usr/bin/env python3
"""Install an isolated Operon CLI/API/MCP server; standard-library bootstrap only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import urllib.request
import uuid

OWNER = 'Operon.Server.Install.v1'
REPOSITORY = 'https://api.github.com/repos/lovegavin/Operon'


def no_links(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'Installation paths cannot contain symbolic links: {part}')
    return path


def receipt(root):
    marker = root / 'operon-install.json'
    if not marker.is_file():
        return None
    value = json.loads(marker.read_text(encoding='utf-8'))
    if value.get('owner') != OWNER:
        raise ValueError(f'Unrecognized installation receipt: {marker}')
    return value


def destination(selected):
    root = no_links(Path(selected).expanduser())
    if root.is_file():
        raise ValueError(f'Choose a directory, not a file: {root}')
    def available(path):
        no_links(path)
        if path.is_file():
            return False
        if not path.exists() or not any(path.iterdir()):
            return True
        return receipt(path) is not None
    if available(root):
        return root
    suffix = 1
    while True:
        child = root / ('Operon' if suffix == 1 else f'Operon-{suffix}')
        if available(child):
            return child
        suffix += 1


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def download(url, path, digest=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'Operon-server-setup'})
    checksum = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, path.open('wb') as target:
        while block := response.read(1024 * 1024):
            target.write(block)
            checksum.update(block)
    if digest and checksum.hexdigest() != digest:
        raise ValueError(f'Checksum mismatch: {path.name}')


def release_wheels(version, directory):
    if version != 'latest' and not re.fullmatch(r'v?\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?', version):
        raise ValueError('Use latest or an explicit release version such as 3.0.0')
    endpoint = '/releases/latest' if version == 'latest' else '/releases/tags/v' + version.removeprefix('v')
    metadata = directory / 'release.json'
    download(REPOSITORY + endpoint, metadata)
    data = json.loads(metadata.read_text(encoding='utf-8'))
    wheels = []
    for prefix in ('operon_studio-', 'operon_builtin_library-'):
        assets = [item for item in data['assets'] if item['name'].startswith(prefix) and item['name'].endswith('-py3-none-any.whl')]
        if len(assets) != 1:
            raise ValueError(f'Release must contain exactly one {prefix} wheel')
        asset = assets[0]
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', asset.get('digest') or ''):
            raise ValueError(f'Release asset has no SHA256 digest: {asset["name"]}')
        url = asset['browser_download_url']
        if not url.startswith('https://github.com/lovegavin/Operon/releases/download/'):
            raise ValueError('Unexpected release download location')
        target = directory / Path(asset['name']).name
        download(url, target, asset['digest'].split(':', 1)[1])
        wheels.append(target)
    return wheels


def child_environment():
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('PYTHON', 'CONDA', 'MAMBA', 'OPERON_', 'OPERON_', 'PIP_'))
                   and key not in ('VIRTUAL_ENV', '_CE_CONDA', '_CE_M')}
    environment.update(PYTHONNOUSERSITE='1', PIP_CONFIG_FILE=os.devnull)
    return environment


def publish(root, attempt, document, result, content):
    launcher = no_links(root / 'bin/operon')
    launcher.parent.mkdir(exist_ok=True)
    old = receipt(root) or {}
    if launcher.exists() and old.get('launcher_sha256') != hashlib.sha256(launcher.read_bytes()).hexdigest():
        raise ValueError(f'Existing launcher was modified; preserve it and choose another prefix: {launcher}')
    destinations = [launcher, no_links(root / 'server.json'), no_links(root / 'operon-install.json')]
    previous = {path: (path.read_bytes(), path.stat().st_mode) if path.exists() else None for path in destinations}
    result['launcher_sha256'] = hashlib.sha256(content.encode('utf-8')).hexdigest()
    try:
        temporary = attempt / 'operon-launcher'
        temporary.write_text(content, encoding='utf-8'); temporary.chmod(0o700)
        os.replace(temporary, launcher)
        atomic_json(root / 'server.json', document)
        atomic_json(root / 'operon-install.json', result)
    except BaseException:
        # An ordinary write error or Ctrl+C must not leave an old install pointing
        # at half-published state. Runtime directories themselves are immutable.
        for path, saved in previous.items():
            if saved is None:
                path.unlink(missing_ok=True)
            else:
                temporary = attempt / ('restore-' + uuid.uuid4().hex)
                temporary.write_bytes(saved[0]); temporary.chmod(saved[1])
                os.replace(temporary, path)
        raise


def install(args):
    if sys.platform != 'linux':
        raise ValueError('Use Operon_Setup.exe --quiet for a Windows installation')
    import fcntl
    root = destination(args.prefix)
    root.mkdir(parents=True, exist_ok=True)
    # A kernel lock is released on crashes; there is no stale-lock reset step.
    lock = no_links(root / '.install.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        raise ValueError(f'Another installer is using {root}') from None
    with lock:
        old = receipt(root)
        if old is None:
            atomic_json(root / 'operon-install.json', {'owner': OWNER, 'status': 'preparing'})
        # Never mutate a previous runtime. Failed attempts retain their log and
        # the previously published server document/launcher remain usable.
        attempt = root / 'versions' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8])
        no_links(attempt).mkdir(parents=True)
        log_path = attempt / 'install.log'
        runtime = attempt / 'runtime'
        python = runtime / 'bin/python'
        environment = child_environment()
        def progress(message):
            print(message, file=sys.stderr, flush=True)
            with log_path.open('a', encoding='utf-8') as log:
                log.write(message + '\n')
        def run(command, *, capture=False):
            with log_path.open('a', encoding='utf-8') as log:
                result = subprocess.run(list(map(str, command)), env=environment, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE if capture else log, stderr=log, text=True)
            if result.returncode:
                raise RuntimeError(f'Installation command failed (exit {result.returncode}). See {log_path}')
            return result.stdout
        try:
            progress(f'Install directory: {root}\nInstallation log: {log_path}')
            if args.source:
                source = Path(args.source).expanduser().resolve()
                if not (source / 'pyproject.toml').is_file() or not (source / 'library/pyproject.toml').is_file():
                    raise ValueError('--source must contain the application and library pyproject.toml files')
                packages = [str(source) + '[agent]', str(source / 'library')]
            elif args.app_wheel:
                wheels = [Path(args.app_wheel).expanduser().resolve(), Path(args.library_wheel).expanduser().resolve()]
                if not all(path.is_file() and path.suffix == '.whl' for path in wheels):
                    raise ValueError('Both local wheel files must exist')
                packages = [str(wheels[0]) + '[agent]', str(wheels[1])]
            else:
                progress(f'Downloading checksum-verified {args.version} application and library wheels')
                wheels = release_wheels(args.version, attempt)
                packages = [str(wheels[0]) + '[agent]', str(wheels[1])]
            progress('Preparing an isolated Python runtime')
            if args.manager:
                environment['MAMBA_ROOT_PREFIX'] = str(attempt / 'mamba-cache')
                run([args.manager, '--no-rc', 'create', '-y', '-p', runtime, '--override-channels',
                     '-c', 'https://conda.anaconda.org/conda-forge', 'python=3.11', 'pip'])
            else:
                selected = args.python or sys.executable
                run([selected, '-I', '-c', 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'])
                run([selected, '-I', '-m', 'venv', runtime])
            progress('Installing the application, MCP and reference library; scientific packages are prepared per route')
            pip = [python, '-I', '-m', 'pip', '--isolated', 'install', '--no-input', '--disable-pip-version-check']
            if args.wheel_dir:
                pip += ['--no-index', '--find-links', str(Path(args.wheel_dir).resolve())]
            run([*pip, *packages])
            run([python, '-I', '-m', 'pip', 'check'])
            progress('Checking installed CLI and server registration')
            version = run([python, '-I', '-m', 'operon', '--version'], capture=True).strip()
            workspace = Path(args.workspace).expanduser().resolve() if args.workspace else Path((old or {}).get('workspace', root / 'workspace'))
            # Build the new server document separately, then atomically publish it.
            pending = attempt / 'registration'
            run([python, '-I', '-m', 'operon.remote.installation', 'register', '--base', pending,
                 '--workspace', workspace], capture=True)
            document = json.loads((pending / 'server.json').read_text(encoding='utf-8'))
            no_links(root / 'server.json')
            if (root / 'server.json').exists():
                previous = json.loads((root / 'server.json').read_text(encoding='utf-8'))
                document['server_id'] = previous['server_id']
            launcher = root / 'bin/operon'
            content = '#!/bin/sh\nexec ' + shlex.quote(str(python)) + ' -I -m operon --workspace ' + shlex.quote(str(workspace)) + ' "$@"\n'
            result = {'owner': OWNER, 'status': 'installed', 'version': version,
                      'install_dir': str(root), 'python': str(python), 'workspace': str(workspace),
                      'server_document': str(root / 'server.json'), 'command': str(launcher), 'log': str(log_path)}
            publish(root, attempt, document, result, content)
            progress('Installation complete. Use the command in the JSON result; no desktop is required.')
            return result
        except (Exception, KeyboardInterrupt) as error:
            error.install_log = str(log_path)
            error.install_dir = str(root)
            progress('Installation failed; existing runtimes and workflow data were retained.')
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', default=str(Path.home() / '.local/share/operon/server'))
    parser.add_argument('--workspace', help='Data workspace; defaults to INSTALL_DIR/workspace')
    parser.add_argument('--version', default='latest', help='Release version; default latest stable')
    packages = parser.add_mutually_exclusive_group()
    packages.add_argument('--source', help='Install a source checkout including its library directory')
    packages.add_argument('--app-wheel', help='Install a local application wheel instead of downloading')
    parser.add_argument('--library-wheel', help='Independent library wheel, required with --app-wheel')
    parser.add_argument('--wheel-dir', help='Offline dependency wheel directory; disables package indexes')
    parser.add_argument('--python', help='Python 3.11+ to use as the isolated venv base')
    parser.add_argument('--manager', help=argparse.SUPPRESS)
    parser.add_argument('--result', help='Also save the final JSON result here')
    args = parser.parse_args(argv)
    if bool(args.app_wheel) != bool(args.library_wheel):
        parser.error('--app-wheel and --library-wheel must be supplied together')
    try:
        result = install(args)
        status = 0
    except (Exception, KeyboardInterrupt) as error:
        result = {'status': 'failed', 'message': str(error) or 'Installation interrupted',
                  'log': getattr(error, 'install_log', None), 'install_dir': getattr(error, 'install_dir', None)}
        status = 1
    if args.result:
        output = Path(args.result).expanduser().absolute()
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            atomic_json(output, result)
        except OSError as error:
            result = {**result, 'installation_status': result['status'], 'status': 'failed',
                      'message': f'Could not save result file {output}: {error}'}
            status = 1
    print(json.dumps(result, ensure_ascii=False))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
