"""Build PDBFixer's pure Python wheel from a checksum-pinned official release.

PDBFixer publishes source on GitHub/conda-forge, not PyPI. Run this at release
build time and pass the output to build_runtime.py --wheelhouse/--bundle-wheels.
OpenMM itself is resolved from its platform wheel. No recipient compilation.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REVISION = '94cfa4c0ca551cdc5f13320f9a658efd59f2b881'
URL = f'https://codeload.github.com/openmm/pdbfixer/zip/{REVISION}'
SHA256 = '466e14f712f8a609820f44b9651f495c08c9abd159464d3d37b3d2ccbdb24005'


def build(output, archive=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pdbfixer-build-') as temporary:
        temporary = Path(temporary)
        source = Path(archive) if archive else temporary / 'source.zip'
        if not archive:
            with urllib.request.urlopen(URL, timeout=90) as response:
                source.write_bytes(response.read())
        if hashlib.sha256(source.read_bytes()).hexdigest() != SHA256:
            raise ValueError('PDBFixer source checksum mismatch')
        with zipfile.ZipFile(source) as package:
            for name in package.namelist():
                if not (temporary / name).resolve().is_relative_to(temporary):
                    raise ValueError('Unsafe source archive path')
            package.extractall(temporary)
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-cache-dir',
                        '--no-build-isolation', '--wheel-dir', str(output),
                        str(temporary / f'pdbfixer-{REVISION}')], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path, help='Optional already-downloaded official source ZIP')
    args = parser.parse_args()
    build(args.output, args.archive)
