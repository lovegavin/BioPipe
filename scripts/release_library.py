"""Build the library with an installed, released application, never checkout code.

Run with ``python -I scripts/release_library.py --output build/library``.
The application and library have independent versions and Git tag namespaces.
"""
import argparse
import json
from pathlib import Path
import sys
import platform
import zipfile

from packaging.version import Version


def configuration(root, tag=None):
    value = json.loads((root / 'library/release.json').read_text(encoding='utf-8'))
    for key in ('version', 'minimum_application', 'build_application'):
        if str(Version(value[key])) != value[key]:
            raise ValueError(f'{key} must be a canonical version')
    if value['minimum_application'] != value['build_application']:
        raise ValueError('Build and verify with the minimum supported application')
    if tag is not None and tag != 'library-v' + value['version']:
        raise ValueError('Library tag differs from library/release.json')
    return value


def released_application(root, config):
    import biopipe
    if not sys.flags.isolated:
        raise ValueError('Use python -I to exclude checkout and user Python paths')
    if Path(biopipe.__file__).resolve().parent == (root / 'biopipe').resolve():
        raise ValueError('Install the released application; do not build with the source checkout')
    if biopipe.__version__ != config['build_application']:
        raise ValueError(f"Expected released BioPipe {config['build_application']}; got {biopipe.__version__}")


def build(root, output, tag=None):
    config = configuration(root, tag)
    released_application(root, config)
    from biopipe.library_bundle import build_bundle, sha256
    source = root / 'library/seed'
    result = build_bundle(source if source.is_dir() else root, output, config['version'])
    path = Path(result['bundle'])
    # This is a transport compatibility bound, not an operator protocol change.
    # Released builders may have an older default bound than this library needs.
    temporary = path.with_suffix('.pending')
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == 'library.json':
                document = json.loads(data)
                document['minimum_application'] = config['minimum_application']
                data = json.dumps(document, indent=2).encode()
            target.writestr(item, data)
    temporary.replace(path)
    # The released v2.0.4 installer compares rebuilt wheel ZIP bytes. Its ZIP
    # metadata is OS-specific, so publish a native envelope for each platform.
    system = platform.system()
    if system not in {'Windows', 'Linux'}:
        raise ValueError('Official library bundles currently target Windows and Linux')
    native = path.with_name(f'BioPipe-Library-v{config["version"]}-{system}.biopipe-library.zip')
    path.replace(native)
    path = native
    result['bundle'] = str(path)
    result.update(sha256=sha256(path), minimum_application=config['minimum_application'],
                  build_application=config['build_application'], tag='library-v' + config['version'])
    (output / f'SHA256SUMS-{system}.txt').write_text(f"{result['sha256']}  {path.name}\n", encoding='utf-8')
    (output / 'library-build.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tag')
    args = parser.parse_args()
    print(json.dumps(build(args.source.resolve(), args.output.resolve(), args.tag), indent=2))
