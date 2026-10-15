"""Package an already-built Windows host and Python source, without user data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib
import zipfile
import urllib.request

from audit_portability import audit_files


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', type=Path, default=root / 'dist/BioPipe Studio')
    parser.add_argument('--output', type=Path, default=root / 'dist/releases')
    parser.add_argument('--runtime', type=Path, help='Portable Python directory produced by build_runtime.py')
    parser.add_argument('--webview-bootstrapper', type=Path, help='Optional cached official Microsoft WebView2 bootstrapper; signature is verified')
    parser.add_argument('--lite', action='store_true', help='Explicit legacy package requiring an existing Python environment')
    args = parser.parse_args()
    if not args.lite and (not args.runtime or not (args.runtime / 'biopipe-runtime.json').is_file()):
        parser.error('Full releases require --runtime from build_runtime.py; use --lite only for an environment-free package')
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    name = f'BioPipe-Studio-v{version}-Windows-x64'
    destination = args.output.resolve() / name
    if destination.exists():
        parser.error(f'Output already exists: {destination}')
    if not (args.desktop / 'BioPipe Studio.exe').is_file():
        parser.error('Build the desktop host first.')
    destination.mkdir(parents=True)

    def copy(source, rel):
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    copy(args.desktop / 'BioPipe Studio.exe', 'BioPipe Studio.exe')
    if not args.lite:
        shutil.copytree(args.runtime, destination / 'runtime/python', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        bootstrapper = destination / 'runtime/MicrosoftEdgeWebview2Setup.exe'
        url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703'
        if args.webview_bootstrapper:
            shutil.copy2(args.webview_bootstrapper, bootstrapper)
        else:
            with urllib.request.urlopen(url, timeout=90) as response, bootstrapper.open('wb') as output:
                shutil.copyfileobj(response, output)
        # Verify the executable's Authenticode signature before redistribution.
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                        root / 'scripts/verify_microsoft_signature.ps1', str(bootstrapper)], check=True)
        (destination / 'runtime/webview2.json').write_text(json.dumps({'source': url,
            'sha256': hashlib.sha256(bootstrapper.read_bytes()).hexdigest()}), encoding='utf-8')
    shutil.copytree(root / 'frontend/dist', destination / 'frontend')
    for directory in ('src', 'biopipe', 'biopipe_sdk'):
        for source in (root / directory).rglob('*'):
            if source.is_file() and source.suffix.lower() in {'.py', '.json', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'}:
                copy(source, source.relative_to(root))
    for source in (root / 'tasks').rglob('*'):
        if source.is_file() and source.suffix in {'.py', '.yaml', '.yml'} and 'output' not in source.relative_to(root).parts:
            copy(source, source.relative_to(root))
    for source in (root / 'routes').rglob('*'):
        if source.is_file() and source.suffix in {'.json', '.yaml', '.yml'}:
            copy(source, source.relative_to(root))
    for source in root.glob('requirements*.txt'):
        copy(source, source.name)
    for source in root.glob('constraints*.txt'):
        copy(source, source.name)
    for name_ in ('README.md', 'pyproject.toml'):
        copy(root / name_, name_)
    for name_ in ('desktop_server.py', 'run.py'):
        copy(root / 'scripts' / name_, Path('scripts') / name_)
    shutil.copytree(root / 'docs', destination / 'docs')
    # Ship the small source example referenced by the hot-refresh guide.
    shutil.copytree(root / 'examples/dropins', destination / 'examples/dropins',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(root / 'THIRD_PARTY_NOTICES', destination / 'THIRD_PARTY_NOTICES')
    # Regenerate frontend notices from the lockfile actually used for this build.
    lock = json.loads((root / 'frontend/package-lock.json').read_text(encoding='utf-8'))
    notices = ['Licenses for bundled frontend dependencies.\n']
    for directory, meta in sorted(lock['packages'].items()):
        if not directory or (meta.get('dev') and directory not in ('node_modules/tailwindcss', 'node_modules/vite')):
            continue
        module = root / 'frontend' / directory
        licenses = [p for p in module.iterdir() if p.is_file() and p.name.lower().startswith(('license', 'notice', 'copying'))]
        if not licenses:
            raise RuntimeError(f'Missing license text for {directory}')
        notices.append(f'\n{"=" * 72}\n{directory} {meta["version"]}\n')
        notices.extend(p.read_text(encoding='utf-8-sig') for p in sorted(licenses))
    (destination / 'THIRD_PARTY_NOTICES/frontend-licenses.txt').write_text('\n'.join(notices), encoding='utf-8')
    (destination / 'biopipe-desktop.json').write_text(json.dumps({
        'backendRoot': '.', 'python': 'auto', 'entryPoint': 'scripts/desktop_server.py', 'frontend': 'frontend',
        'bundledRuntime': not args.lite,
    }, indent=2) + '\n', encoding='utf-8')
    (destination / 'START_HERE.txt').write_text(f'''BioPipe Studio {version} - Windows x64

1. Extract this entire folder. Keep the executable and adjacent files together.
2. Double-click BioPipe Studio.exe. An existing BioPipe environment is discovered
   automatically, including remembered environments and registered Conda/Python.
   If prompted, select your environment's python.exe; the choice is remembered.
3. If this computer has no suitable environment, install Python 3.11 or 3.12 and
   Microsoft Edge WebView2 Runtime as needed, then create/configure an environment:
   python -m venv .venv
   For Python 3.11 on Windows x64:
   .venv\\Scripts\\python.exe -m pip install -c constraints-py311-windows.txt -e ".[agent]"
   For Python 3.12 on Windows x64, use constraints-py312-windows.txt instead.
4. Double-click BioPipe Studio.exe again.

Studio checks declared Reader and operator dependencies at startup and library
refresh. Compatible dependencies share the runtime; version conflicts use private
dependency directories and subprocesses with the same Python executable.
Missing dependencies need internet access. Native packages may require supported
Windows wheels or build tools; Library Management retains the exact error.
The constraints cover core Studio, MCP and development tools. Optional analysis
and native reader dependencies have separate requirements. See docs/installation.md.
Existing environments may be selected with BIOPIPE_PYTHON or biopipe-desktop.json.
To select an interpreter again, use BioPipe Studio.exe --select-runtime.
The local runtime hint ~/.biopipe/runtime.json is never included in this package.
Python and analysis dependencies are not bundled; .NET and the UI are bundled.
User data and route registries are stored under ~/.biopipe/studio by default.
Start Studio before connecting your own agent through MCP. See docs/agent_api.md.
There is no bundled AI service. Graph edits do not execute analyses.
''', encoding='utf-8')
    if not args.lite:
        (destination / 'START_HERE.txt').write_text(f'''BioPipe Studio {version} - Windows x64 (bundled environment)

1. Extract the entire archive to a folder where your account can read files.
2. Double-click BioPipe Studio.exe. No Python or Conda installation is required.
3. If WebView2 is missing, its official Microsoft bootstrapper installs it for
   your account automatically. This one-time step requires internet access.

The runtime/python folder contains the tested Python runtime and CPU dependencies.
Keep it beside the executable. Python/Conda from another project is not modified.
Studio checks declared operator/Reader dependencies once per session, keeps
successful checks, and repairs missing dependencies in immutable target directories.
Only conflicting operators use private dependencies and a subprocess with the
same Python executable; compatible operators continue sharing the runtime.
New dependencies need internet access. Existing bundled analyses work offline.
User graphs, dependency targets and logs use the shared Studio profile.
See docs/installation.md, docs/reader_extensions.md and docs/step_extensions.md.
''', encoding='utf-8')
    audit = audit_files((p for p in destination.rglob('*') if p.is_file()
                        and not {'THIRD_PARTY_NOTICES', 'runtime'}.intersection(p.relative_to(destination).parts)), destination)
    if audit['findings']:
        raise RuntimeError('Developer paths in release: ' + json.dumps(audit['findings']))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    manifest = {'version': version, 'source_commit': commit, 'python_bundled': not args.lite, 'files': []}
    for file in sorted(destination.rglob('*')):
        if file.is_file():
            manifest['files'].append({'path': file.relative_to(destination).as_posix(), 'bytes': file.stat().st_size,
                                      'sha256': hashlib.sha256(file.read_bytes()).hexdigest()})
    (destination / 'package-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    archive = destination.parent / (name + '.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for file in sorted(destination.rglob('*')):
            if file.is_file():
                output.write(file, (Path('BioPipe Studio') / file.relative_to(destination)).as_posix())
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
    print(json.dumps({'archive': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': len(manifest['files'])}))


if __name__ == '__main__':
    main()
