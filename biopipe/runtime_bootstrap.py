"""Stdlib-only entry point: choose dependency paths before importing the SDK.

Invoked with the host's Python -I -S. No venv, user site, .pth execution or
PYTHONPATH mutation is needed. The configuration belongs to a local transaction.
"""
import json
import importlib.util
import os
from pathlib import Path
import runpy
import sys


def main():
    sys.dont_write_bytecode = True
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8', errors='replace')
    config, module, *arguments = sys.argv[1:]
    paths = json.loads(Path(config).read_text(encoding='utf-8'))['paths']
    sys.path[:] = list(dict.fromkeys([*paths, *sys.path]))
    if module == 'pip' and importlib.util.find_spec('pip') is None:
        # uv and other environment creators can omit pip. Run CPython's bundled
        # installer wheel directly, as ensurepip itself does, without installing
        # into the user's base environment or creating another interpreter.
        try:
            import ensurepip
            wheels = list((Path(ensurepip.__file__).parent / '_bundled').glob('pip-*.whl'))
        except ImportError:
            wheels = []
        if not wheels:
            raise RuntimeError('Dependency installation requires pip. This Python has neither pip nor a bundled ensurepip wheel; install pip in the selected Python environment.')
        wheel = max(wheels, key=lambda p: tuple(int(v) for v in p.name.split('-')[1].split('.')))
        sys.path.insert(0, str(wheel))
    os.environ['BIOPIPE_REGISTRY_MAINTENANCE'] = '1'
    sys.argv = [module, *arguments]
    runpy.run_module(module, run_name='__main__')


if __name__ == '__main__':
    main()
