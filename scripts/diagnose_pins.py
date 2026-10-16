"""Read-only pin diagnostics using the same profile selection as Studio."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    from biopipe.packages import bundled_state
    from src.web.profile import resolve_profile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-dir', type=Path)
    parser.add_argument('--workspace', type=Path)
    args = parser.parse_args()
    profile = resolve_profile(ROOT, profile_dir=args.profile_dir, workspace=args.workspace)
    current = {d['id']: d['implementation'] for d in bundled_state()['descriptors']}
    print(f'read-only profile diagnostics: {profile.data_dir}')
    print('Historical OLD locks are provenance, not files to overwrite. New Studio runs resolve known bundled source updates.')

    def visit(value):
        if isinstance(value, dict):
            for name, item in value.items():
                if name == 'plugin_lock' and isinstance(item, dict):
                    yield from item.items()
                else:
                    yield from visit(item)
        elif isinstance(value, list):
            for item in value:
                yield from visit(item)

    for path in sorted(profile.data_dir.rglob('*.json')):
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
            pins = list(visit(value))
            if path.name == 'plugins.lock.json' and isinstance(value, dict):
                pins.extend((d['id'], d['implementation']) for d in value.get('descriptors', [])
                            if d.get('origin') == 'bundled')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'[unreadable] {path}: {exc}')
            continue
        old = sorted({key for key, pin in pins if key in current and pin != current[key]})
        if old:
            print(f'[OLD] {path.relative_to(profile.data_dir)}: {", ".join(old)}')


if __name__ == '__main__':
    main()
