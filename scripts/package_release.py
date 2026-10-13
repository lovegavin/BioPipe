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


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--desktop', type=Path, default=root / 'dist/BioPipe Studio')
    parser.add_argument('--output', type=Path, default=root / 'dist/releases')
    args = parser.parse_args()
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
    shutil.copytree(root / 'frontend/dist', destination / 'frontend')
    for directory in ('src', 'biopipe', 'biopipe_sdk'):
        for source in (root / directory).rglob('*'):
            if source.is_file() and source.suffix in {'.py', '.json'}:
                copy(source, source.relative_to(root))
    for source in (root / 'tasks').rglob('*'):
        if source.is_file() and source.suffix in {'.py', '.yaml', '.yml'} and 'output' not in source.relative_to(root).parts:
            copy(source, source.relative_to(root))
    for source in (root / 'routes').rglob('*'):
        if source.is_file() and source.suffix in {'.json', '.yaml', '.yml'}:
            copy(source, source.relative_to(root))
    for source in root.glob('requirements*.txt'):
        copy(source, source.name)
    for name_ in ('README.md', 'pyproject.toml'):
        copy(root / name_, name_)
    for name_ in ('desktop_server.py', 'run.py'):
        copy(root / 'scripts' / name_, Path('scripts') / name_)
    shutil.copytree(root / 'docs', destination / 'docs')
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
        'backendRoot': '.', 'python': 'auto', 'entryPoint': 'scripts/desktop_server.py', 'frontend': 'frontend'
    }, indent=2) + '\n', encoding='utf-8')
    (destination / 'START_HERE.txt').write_text(f'''BioPipe Studio {version} - Windows x64

1. Extract this entire folder. Keep the executable and adjacent files together.
2. Install Python 3.11+ and Microsoft Edge WebView2 Runtime if needed.
3. In this folder, create/configure your Python environment:
   python -m venv .venv
   .venv\\Scripts\\python.exe -m pip install -e ".[agent]"
4. Double-click BioPipe Studio.exe.

For survival analysis and DESeq2, install requirements-analysis.txt in that environment.
For optional input formats, install requirements-readers.txt as needed.
Existing environments may be selected with BIOPIPE_PYTHON or biopipe-desktop.json.
Python and analysis dependencies are not bundled; .NET and the UI are bundled.
User data and route registries are stored under ~/.biopipe/studio by default.
Start Studio before connecting your own agent through MCP. See docs/agent_api.md.
There is no bundled AI service. Graph edits do not execute analyses.
''', encoding='utf-8')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    manifest = {'version': version, 'source_commit': commit, 'python_bundled': False, 'files': []}
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
