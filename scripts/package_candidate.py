"""Deliver Setup, instructions, fixtures and checksums in one test-machine ZIP."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import tempfile
import tomllib
import zipfile


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def package_candidate(root, setup, output, *, label, evidence=()):
    root, setup, output = (Path(path).resolve() for path in (root, setup, output))
    if not re.fullmatch(r'[A-Za-z0-9._-]+', label):
        raise ValueError('Candidate label must be a simple filename component')
    if output.exists():
        raise ValueError('Candidate archive already exists; use a new filename')
    required = ('docs/OPERON_3_TEST_ACCEPTANCE.md', 'docs/OPERON_3_TEST_INSTRUCTIONS_ZH.md',
                'scripts/verify_release_agent.md', 'examples/workflows/script_pipeline/workflow.yaml')
    for relative in required:
        if not (root / relative).is_file():
            raise ValueError('Missing acceptance material: ' + relative)
    expected = setup.with_suffix('.exe.sha256').read_text(encoding='utf-8').split()[0]
    if digest(setup) != expected:
        raise ValueError('Setup does not match its checksum sidecar')
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='candidate-', dir=output.parent) as temporary:
        bundle = Path(temporary) / f'Operon-{version}-{label}-test'
        bundle.mkdir()
        shutil.copy2(setup, bundle / 'Operon_Setup.exe')
        shutil.copy2(setup.with_suffix('.exe.sha256'), bundle / 'Operon_Setup.exe.sha256')
        shutil.copytree(root / 'docs', bundle / 'docs')
        shutil.copytree(root / 'examples', bundle / 'examples',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'build', 'dist', '*.egg-info'))
        shutil.copytree(root / 'examples/workflows/script_pipeline', bundle / 'script_pipeline',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (bundle / 'scripts').mkdir()
        shutil.copy2(root / 'scripts/verify_release_agent.md', bundle / 'scripts/verify_release_agent.md')
        instructions = (root / required[1]).read_text(encoding='utf-8')
        instructions = instructions.replace('同包 `OPERON_3_TEST_ACCEPTANCE.md`', '同包 `docs/OPERON_3_TEST_ACCEPTANCE.md`')
        (bundle / 'FORWARD_TO_TESTER.txt').write_text(instructions, encoding='utf-8')
        (bundle / 'START_HERE.txt').write_text(
            f'Operon {version} {label} test candidate\n\n'
            'Extract this entire archive. Check SHA256SUMS.txt before double-clicking Operon_Setup.exe.\n'
            'Forward FORWARD_TO_TESTER.txt to the test-machine chat. Do not transfer only Setup.\n'
            'Use a new test directory and preserve all previous programs, profiles and evidence.\n'
            'This is a candidate. Interactive acceptance is required; do not publish.\n', encoding='utf-8')
        if evidence:
            (bundle / 'evidence').mkdir()
            for source in evidence:
                source = Path(source)
                target = bundle / 'evidence' / source.name
                if target.exists():
                    raise ValueError('Duplicate evidence filename: ' + source.name)
                shutil.copy2(source, target)
        files = sorted(path for path in bundle.rglob('*') if path.is_file())
        (bundle / 'SHA256SUMS.txt').write_text(''.join(
            f'{digest(path)}  {path.relative_to(bundle).as_posix()}\n' for path in files), encoding='utf-8')
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(bundle.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle.parent).as_posix(),
                                  compress_type=zipfile.ZIP_STORED if path.suffix == '.exe' else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Candidate archive CRC verification failed')
    checksum = digest(output)
    output.with_suffix(output.suffix + '.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    return {'archive': str(output), 'sha256': checksum, 'bytes': output.stat().st_size}


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(package_candidate(Path(__file__).resolve().parents[1], args.setup, args.output,
                                      label=args.label, evidence=args.evidence)))
