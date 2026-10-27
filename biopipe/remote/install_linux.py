"""Managed server installer. Invoked only inside the isolated deployment prefix."""
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib


def requirements(code):
    project = tomllib.loads((code / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    manifest = json.loads((code / 'biopipe/builtin_packages.json').read_text(encoding='utf-8'))
    entries = [d for p in manifest['packages'] for d in p['descriptors']]
    specs = sorted(set(project['dependencies']) | {r for d in entries for r in d.get('dependencies', [])})
    hic = [line.strip() for line in (code / 'requirements-hic-linux.txt').read_text().splitlines()
           if line.strip() and not line.startswith('#')]
    return specs + hic, entries


def ensure_requirements(specs, request):
    """Repair the complete dependency graph, including missing transitive libraries."""
    from packaging.requirements import Requirement
    missing = []
    for spec in specs:
        req = Requirement(spec)
        if req.marker and not req.marker.evaluate():
            continue
        try:
            if req.specifier and not req.specifier.contains(metadata.version(req.name), prereleases=True):
                missing.append(spec)
        except metadata.PackageNotFoundError:
            missing.append(spec)
    request.write_text('\n'.join(specs) + '\n', encoding='utf-8')
    health = subprocess.run([sys.executable, '-I', '-m', 'pip', 'check'], capture_output=True, text=True)
    if missing or health.returncode:
        print(f'Repairing dependencies ({len(missing)} direct requirements missing or incompatible)', flush=True)
        # One pip solve for all Python libraries: do not preinstall conda's
        # NumPy-1 Hi-C builds then replace NumPy underneath their binary ABI.
        # micromamba supplies only Python, native tools and build compilers.
        subprocess.run([sys.executable, '-I', '-m', 'pip', '--isolated', 'install',
                        '--disable-pip-version-check', '-r', str(request)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--digest', required=True)
    args = parser.parse_args()
    code = args.code.resolve()
    sys.path.insert(0, str(code))
    prefix = Path(sys.prefix).resolve()
    if sys.platform != 'linux' or not prefix.name.startswith('env-') or prefix.parent.name != 'managed-v1':
        raise ValueError('Installer only writes to a BioPipe managed Linux environment')
    specs, entries = requirements(code)
    ensure_requirements(specs, prefix / 'biopipe-requirements.txt')
    # Install the SDK distribution metadata (without altering the dependency plan).
    receipt = prefix / 'biopipe-ready.json'
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if previous.get('source_sha256') != args.digest:
        subprocess.run([sys.executable, '-I', '-m', 'pip', '--isolated', 'install', '--no-deps', str(code)], check=True)
    subprocess.run([sys.executable, '-I', '-m', 'pip', 'check'], check=True)
    from biopipe.dependencies import probe
    results = probe(entries)
    failed = {k: v['error'] for k, v in results.items() if v['status'] != 'passed'}
    if failed:
        raise ValueError('Operator dependency checks failed: ' + json.dumps(failed))
    for name, command, allowed in [
        ('bwa', ['bwa'], (1,)), ('samtools', ['samtools', '--version'], (0,)),
        ('pairtools', ['pairtools', '--version'], (0,)), ('cooler', ['cooler', '--version'], (0,)),
        ('cooltools', ['cooltools', '--version'], (0,))]:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode not in allowed:
            raise ValueError(name + ' check failed: ' + (result.stdout + result.stderr)[-2000:])
        print(name + ': ready', flush=True)
    value = {'source_sha256': args.digest, 'python': sys.version, 'operators_checked': len(results),
             'packages': {d.metadata['Name']: d.version for d in metadata.distributions()}}
    temporary = receipt.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, receipt)
    print('BioPipe and Hi-C environment ready', flush=True)


if __name__ == '__main__':
    main()
