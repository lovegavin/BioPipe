"""Verify a Setup-owned runtime and resolve its new, isolated profile."""
import argparse
from contextlib import redirect_stdout
import faulthandler
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Optional report copy for command-line diagnostics')
    parser.add_argument('--trace-stalls', action='store_true', help='Record Python stacks if inspection stalls')
    args = parser.parse_args()
    from src.web.profile import resolve_profile
    from src.web.storage import atomic_json
    report = {'schema_version': 1, 'status': 'ready', 'issues': []}
    if args.trace_stalls:
        faulthandler.dump_traceback_later(30, repeat=True)
    try:
        if not (ROOT / 'operon-install.json').is_file():
            raise ValueError('Setup installation identity is missing.')
        if sys.version_info < (3, 11):
            raise RuntimeError('Operon requires Python 3.11 or later.')
        if Path(sys.executable).resolve() != (ROOT / 'runtime/python/python.exe').resolve():
            raise RuntimeError('Setup must use the runtime inside the new installation.')
        from operon.runtime import CORE_MODULES
        for module in CORE_MODULES:
            print('[Operon setup] Checking ' + module, file=sys.stderr, flush=True)
            with redirect_stdout(sys.stderr):
                importlib.import_module(module)
        profile = resolve_profile(ROOT)
        if profile.profile_dir.exists():
            raise ValueError('The new installation profile already exists; rerun Setup.')
        report['profile'] = profile.as_dict()
    except Exception as error:
        report.update(status='blocked', issues=[{'type': type(error).__name__, 'message': str(error)}])
    finally:
        if args.trace_stalls:
            faulthandler.cancel_dump_traceback_later()
    report['runtime'] = {'python': sys.executable, 'version': sys.version.split()[0]}
    # The native installer owns its log directory. Return the small report over
    # stdout so a child-specific filesystem denial cannot stall installation.
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if args.report:
        atomic_json(args.report.resolve(), report)
    return 2 if report['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
