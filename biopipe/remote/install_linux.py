"""Managed server installer. Invoked only inside the isolated deployment prefix."""
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


PIP_INDEX = (
    '-i', 'https://pypi.tuna.tsinghua.edu.cn/simple',
    '--trusted-host', 'pypi.tuna.tsinghua.edu.cn',
)
PIP_TRANSFER = (
    '--disable-pip-version-check', '--progress-bar', 'off',
    '--retries', '5', '--timeout', '60',
)
PIP_CONSTRAINTS = (
    'pyarrow<22',   # newer sdists drop the cp311 wheel and need Arrow C++
    'libcst<1.8',   # newer sdists are Rust builds; 1.7 ships cp311 wheels
)
# pysam wheels need glibc >= 2.28 on manylinux, so old HPC hosts get it from
# conda-forge/bioconda together with the rest of the native stack.
# antifold 0.3.x pins numpy==1.26.*, which conflicts with pydeseq2>=0.5 (numpy>=2);
# it lives in a dedicated environment and is selected with python_executable.
# pdbfixer needs openmm>=8.2, and PyPI ships openmm 8.1.1 wheels built for NumPy 1;
# MD/energy operators are an optional conda-forge extra (see docs/agent_environment_repair.md).
CONDA_PROVIDED = frozenset({'pdbfixer', 'openmm', 'pysam', 'antifold'})
# Missing imports for these extras are reported, not fatal for the install.
OPTIONAL_MODULES = ('pdbfixer', 'openmm', 'antifold')


def requirements(code):
    project = tomllib.loads((code / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    manifest = json.loads((code / 'biopipe/builtin_packages.json').read_text(encoding='utf-8'))
    entries = [d for p in manifest['packages'] for d in p['descriptors']]
    Requirement = _requirement_class()
    specs = sorted(set(project['dependencies']) | {r for d in entries for r in d.get('dependencies', [])})
    specs = [spec for spec in specs if Requirement(spec).name.lower() not in CONDA_PROVIDED]
    # pdbfixer is published on conda-forge only; installing it with pip aborts
    # the whole resolve. The managed micromamba environment provides it.
    hic = [line.strip() for line in (code / 'requirements-hic-linux.txt').read_text().splitlines()
           if line.strip() and not line.startswith('#')]
    return specs + hic, entries


def pip_command(request, wheel_only, constraints=None, bundle=None):
    """Build a mirror-first pip command, optionally restricted to wheels."""
    command = [sys.executable, '-I', '-m', 'pip', '--isolated', 'install', *PIP_TRANSFER, *PIP_INDEX]
    if wheel_only:
        command.append('--only-binary=:all:')
    else:
        command.append('--prefer-binary')
    if constraints is not None:
        command.extend(['--constraint', str(constraints)])
    if bundle is not None and Path(bundle).is_dir():
        command.extend(['--find-links', str(bundle)])
    command.extend(['-r', str(request)])
    return command


def compiler_environment():
    """Expose the bundled conda-forge toolchain to source builds."""
    environment = dict(os.environ)
    for variable, candidates in (
        ('CC', ('x86_64-conda-linux-gnu-cc', 'gcc', 'cc')),
        ('CXX', ('x86_64-conda-linux-gnu-c++', 'g++', 'c++')),
    ):
        if environment.get(variable):
            continue
        for candidate in candidates:
            resolved = shutil.which(candidate)
            if resolved:
                environment[variable] = resolved
                break
    return environment


def _install(request, wheel_only, environment, constraints=None, bundle=None):
    command = pip_command(request, wheel_only, constraints, bundle)
    result = subprocess.run(command, capture_output=True, text=True, env=environment)
    if result.returncode:
        tail = (getattr(result, 'stdout', '') or '') + (getattr(result, 'stderr', '') or '')
        return result.returncode, tail.strip()[-4000:]
    return 0, ''


def _ensure_compilers():
    """Install the conda-forge toolchain only when a source build is needed."""
    mamba = os.environ.get('BIOPIPE_MAMBA')
    if not mamba or not Path(mamba).is_file():
        return
    subprocess.run(
        [mamba, '--no-rc', 'install', '-y', '-p', sys.prefix, '--override-channels',
         '-c', 'conda-forge', 'gxx_linux-64', 'cmake', 'make'],
        check=False,
    )


def _requirement_class():
    """Return packaging.Requirement, installing packaging when the venv is bare."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        subprocess.run(
            [sys.executable, '-I', '-m', 'pip', '--isolated', 'install', *PIP_TRANSFER, *PIP_INDEX, 'packaging'],
            check=True,
        )
        from packaging.requirements import Requirement
    return Requirement



def split_failures(results):
    """Separate mandatory dependency failures from missing optional extras."""
    failed = {key: value['error'] for key, value in results.items() if value['status'] != 'passed'}
    optional = {
        key: error for key, error in failed.items()
        if any(name in error.lower() for name in OPTIONAL_MODULES)
    }
    required = {key: error for key, error in failed.items() if key not in optional}
    return required, optional

def _ensure_conda_extras():
    """Add conda-only binaries after pip: pysam is needed by several Readers."""
    try:
        import pysam  # noqa: F401
        return True
    except ImportError:
        pass
    mamba = os.environ.get('BIOPIPE_MAMBA')
    if not mamba or not Path(mamba).is_file():
        return False
    result = subprocess.run(
        [mamba, '--no-rc', 'install', '-y', '-p', sys.prefix, '--override-channels',
         '-c', 'conda-forge', '-c', 'bioconda', '--strict-channel-priority', 'pysam=0.22.1'],
        check=False,
    )
    return result.returncode == 0



def ensure_requirements(specs, request, bundle=None):
    """Repair the complete dependency graph, including missing transitive libraries."""
    Requirement = _requirement_class()
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
    constraints = request.with_name('pip-constraints.txt')
    constraints.write_text('\n'.join(PIP_CONSTRAINTS) + '\n', encoding='utf-8')
    health = subprocess.run([sys.executable, '-I', '-m', 'pip', 'check'], capture_output=True, text=True)
    if missing or health.returncode:
        print(f'Repairing dependencies ({len(missing)} direct requirements missing or incompatible)', flush=True)
        # One pip solve for all Python libraries: do not preinstall conda's
        # NumPy-1 Hi-C builds then replace NumPy underneath their binary ABI.
        # micromamba supplies Python, native tools and the build compilers.
        environment = compiler_environment()
        status, tail = _install(request, True, environment, constraints, bundle)
        if status:
            print('No prebuilt wheel for the whole requirement set; '
                  'retrying with source distributions', flush=True)
            status, tail = _install(request, False, environment, constraints, bundle)
        if status:
            print('A source build needs the bundled C/C++ toolchain; retrying', flush=True)
            _ensure_compilers()
            environment = compiler_environment()
            status, tail = _install(request, False, environment, constraints, bundle)
        if status:
            raise RuntimeError('pip install failed after the wheel and source attempts:\n' + tail)
        if not _ensure_conda_extras():
            print(
                'pysam could not be installed; BAM/CRAM/VCF Readers need the '
                'bioconda pysam package',
                flush=True,
            )


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
    ensure_requirements(specs, prefix / 'biopipe-requirements.txt', code / 'biopipe' / 'bundled')
    # Install the SDK distribution metadata (without altering the dependency plan).
    receipt = prefix / 'biopipe-ready.json'
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if previous.get('source_sha256') != args.digest:
        subprocess.run([sys.executable, '-I', '-m', 'pip', '--isolated', 'install', '--no-deps', str(code)], check=True)
    subprocess.run([sys.executable, '-I', '-m', 'pip', 'check'], check=True)
    from biopipe.dependencies import probe
    results = probe(entries)
    required, optional = split_failures(results)
    if required:
        raise ValueError('Operator dependency checks failed: ' + json.dumps(required))
    if optional:
        print(
            'Optional OpenMM extras are not installed; MD/energy operators need '
            'the conda-forge openmm and pdbfixer packages',
            flush=True,
        )
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
    from biopipe.remote.handshake import installation_readiness
    value['dependency_readiness'] = installation_readiness(entries, results)
    temporary = receipt.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, receipt)
    print('BioPipe and Hi-C environment ready', flush=True)


if __name__ == '__main__':
    main()
