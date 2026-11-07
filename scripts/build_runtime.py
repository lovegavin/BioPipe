"""Build the relocatable Windows application runtime (management by default).

Supply a clean python-build-standalone installation, not a venv or developer
environment. Dependencies are resolved here, never on the recipient's first run.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib
import tempfile
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operon.platforms import supported_systems


def windows_descriptors(manifest):
    """Shared Windows dependencies; dedicated runtimes remain separate."""
    return [d for p in manifest['packages'] for d in p['descriptors']
            if 'windows' in supported_systems(d) and not d.get('resources', {}).get('environment')]


def runtime_requirements(project, manifest, mode='management'):
    """Do not make a library update silently enlarge the application runtime."""
    if mode not in {'management', 'analysis'}:
        raise ValueError('Unknown runtime mode: ' + mode)
    specs = set(project['dependencies'] + project['optional-dependencies']['agent'] + ['build>=1.2', 'setuptools>=69'])
    descriptors = windows_descriptors(manifest) if mode == 'analysis' else []
    specs.update(r for descriptor in descriptors for r in descriptor.get('dependencies', []))
    return sorted(specs), descriptors


def build_runtime(source, destination, root, *, wheelhouse=None, offline=False, bundle_wheels=None, mode='management'):
    source, destination, root = map(Path, (source, destination, root))
    if destination.exists():
        raise ValueError(f'Runtime output already exists: {destination}')
    if (source / 'pyvenv.cfg').exists() or not (source / 'python.exe').is_file():
        raise ValueError('Use a Windows python-build-standalone installation, not a virtual environment')
    probe = json.loads(subprocess.check_output([source / 'python.exe', '-I', '-c',
        'import sys,json,struct; print(json.dumps([list(sys.version_info[:3]),struct.calcsize("P")*8]))'], text=True))
    if probe[0][:2] != [3, 11] or probe[1] != 64:
        raise ValueError('This runtime recipe targets CPython 3.11 / Windows x64')
    # Reject a pre-existing developer site-packages directory. The interpreter
    # distribution may include pip/setuptools/wheel, but no project or user code.
    allowed = {'pip', 'setuptools', 'wheel'}
    installed = json.loads(subprocess.check_output([source / 'python.exe', '-I', '-c',
        'import importlib.metadata as m,json; print(json.dumps([d.metadata["Name"].lower() for d in m.distributions()]))'], text=True))
    if set(installed) - allowed:
        raise ValueError('The source interpreter must be clean: ' + ', '.join(sorted(set(installed) - allowed)))
    # This copy is now managed by Operon's release builder, not the uv store.
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'EXTERNALLY-MANAGED'))
    shutil.copy2(root / 'scripts/bundled_paths.pth', destination / 'Lib/site-packages/00_operon_paths.pth')
    shutil.copy2(root / 'scripts/bundled_imports.py', destination / 'Lib/operon_import_paths.py')
    # python-build-standalone's bootstrap pip can retain a direct_url pointing
    # at its CI build directory. Keep the archive hash, not a dead file URL.
    bootstrap_archives = []
    for origin in (destination / 'Lib/site-packages').rglob('direct_url.json'):
        value = json.loads(origin.read_text(encoding='utf-8'))
        bootstrap_archives.append({'distribution': origin.parent.name, 'archive_info': value.get('archive_info', {})})
        origin.unlink()
        record = origin.parent / 'RECORD'
        if record.is_file():
            with record.open(encoding='utf-8', newline='') as stream:
                rows = [row for row in csv.reader(stream) if not row[0].endswith('/direct_url.json')]
            with record.open('w', encoding='utf-8', newline='') as stream:
                csv.writer(stream).writerows(rows)
    python = destination / 'python.exe'
    subprocess.run([python, '-I', '-m', 'ensurepip', '--upgrade'], check=True)
    project = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    manifest = json.loads((root / 'library/seed/operon/builtin_packages.json').read_text(encoding='utf-8'))
    specs, descriptors = runtime_requirements(project, manifest, mode)
    requested = destination / 'operon-requirements.txt'
    requested.write_text('\n'.join(specs) + '\n', encoding='utf-8')
    wheel_options = ['--find-links', str(Path(wheelhouse).resolve())] if wheelhouse else []
    if offline:
        if not wheelhouse:
            raise ValueError('Offline builds require a complete wheelhouse')
        wheel_options += ['--no-index']
    subprocess.run([python, '-I', '-m', 'pip', 'install', '--disable-pip-version-check', *wheel_options,
                    '-c', root / 'constraints-py311-windows.txt', '-r', requested], check=True)
    # Install SDK metadata/code from a wheel without a local direct_url.json or
    # path-bearing console launcher. Operators can then require operon-studio.
    with tempfile.TemporaryDirectory(prefix='operon-wheel-') as temporary:
        # The default build creates an sdist, then builds the wheel from its
        # fresh extraction. A wheel built directly in the checkout can retain
        # deleted modules from an older setuptools build/lib directory.
        subprocess.run([python, '-I', '-m', 'build', '--no-isolation', '--outdir', temporary, root], check=True)
        wheel = next(Path(temporary).glob('*.whl'))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                if name.startswith('/') or '..' in Path(name).parts:
                    raise ValueError('Invalid wheel path')
            archive.extractall(destination / 'Lib/site-packages')
        # The Full distribution explicitly includes a separately versioned seed.
        # Keep it out of the application wheel and remove only this build cache
        # so deleted operators cannot survive a subsequent wheel rebuild.
        library = (root / 'library').resolve()
        cache = (library / 'build').resolve()
        if cache.parent != library or not cache.is_relative_to(root.resolve()):
            raise ValueError('Library build cache escaped the checkout')
        if cache.exists():
            shutil.rmtree(cache)
        subprocess.run([python, '-I', '-m', 'build', '--wheel', '--no-isolation',
                        '--outdir', temporary, library], check=True)
        seed = next(Path(temporary).glob('operon_builtin_library-*.whl'))
        with zipfile.ZipFile(seed) as archive:
            archive.extractall(destination / 'Lib/site-packages')
    subprocess.run([python, '-I', '-m', 'pip', 'check'], check=True)
    versions = json.loads(subprocess.check_output([python, '-I', '-c',
        'import importlib.metadata as m,json; print(json.dumps({d.metadata["Name"]:d.version for d in m.distributions()}))'], text=True))
    (destination / 'operon-lock.txt').write_text('\n'.join(f'{k}=={v}' for k, v in sorted(versions.items()))+'\n', encoding='utf-8')
    from operon.runtime import CORE_MODULES
    imports = sorted(set(CORE_MODULES) | {'mcp'} | {i for d in descriptors for i in d.get('dependency_imports', [])})
    subprocess.run([python, '-I', '-c', 'import importlib; ' + '; '.join(f'importlib.import_module({name!r})' for name in imports)], check=True)
    # Entry-point launchers contain absolute build paths. Studio and the SDK use
    # python -m, so omit them rather than ship launchers that break after moving.
    scripts = destination / 'Scripts'
    if scripts.is_dir():
        for path in scripts.iterdir():
            if path.is_file() and path.suffix in {'.exe', '.py'}:
                path.unlink()
    for path in destination.rglob('direct_url.json'):
        value = json.loads(path.read_text(encoding='utf-8'))
        if value.get('url', '').startswith('file:'):
            raise ValueError(f'Local dependency source is not portable: {path.name}')
    # Locally built native wheels also remain available for later isolated
    # dependency targets. Resolve this directory relative to Python at runtime.
    if bundle_wheels and mode == 'analysis':
        target = destination / 'wheelhouse'
        target.mkdir()
        for path in Path(bundle_wheels).glob('*.whl'):
            shutil.copy2(path, target / path.name)
    # Torch ships a Python 3.12-only compiler test even in its CPython 3.11 wheel.
    # Leave that test as source; all executable application/dependency code is checked.
    subprocess.run([python, '-I', '-m', 'compileall', '-q', '-f',
                    '-x', r'torch[\\/]testing[\\/]_internal[\\/]py312_intrinsics\.py$',
                    '--invalidation-mode', 'unchecked-hash', '-s', str(destination), str(destination / 'Lib')], check=True)
    info = {'schema_version': 1, 'product': 'operon', 'mode': mode, 'application_version': project['version'],
            'python_version': '.'.join(map(str, probe[0])),
            'platform': 'windows-x86_64', 'provider': 'astral-sh/python-build-standalone',
            'bootstrap_archives': bootstrap_archives,
            'included_extensions': sorted(d['id'] for d in descriptors),
            'external_extensions': sorted(d['id'] for p in manifest['packages'] for d in p['descriptors']
                                          if d['id'] not in {item['id'] for item in descriptors}),
            'requirements_sha256': hashlib.sha256(requested.read_bytes()).hexdigest(), 'distributions': versions}
    (destination / 'operon-runtime.json').write_text(json.dumps(info, indent=2)+'\n', encoding='utf-8')
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheelhouse', type=Path, help='Optional directory of previously built and tested native wheels')
    parser.add_argument('--offline', action='store_true', help='Resolve only from the supplied complete wheelhouse')
    parser.add_argument('--bundle-wheels', type=Path, help='Retain these locally built wheels for later dependency repair/isolation')
    parser.add_argument('--mode', choices=['management', 'analysis'], default='management',
                        help='Management-only application runtime by default; analysis is an explicit offline distribution')
    args = parser.parse_args()
    print(json.dumps(build_runtime(args.python_home.resolve(), args.output.resolve(), Path(__file__).resolve().parents[1],
        wheelhouse=args.wheelhouse, offline=args.offline, bundle_wheels=args.bundle_wheels, mode=args.mode)))
