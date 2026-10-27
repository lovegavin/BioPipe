"""Record verified public-release builtin identities without retaining old code.

Use only a trusted, checksum-verified release extraction. This maintenance step
reads declarations/source bytes; it never imports an old operator or runs a job.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def record(source, release, commit, output):
    from biopipe.packages import bundled_state
    from biopipe_sdk.declarations import code_hash
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Use the full verified release commit')
    manifest = json.loads((Path(source) / 'package-manifest.json').read_text(encoding='utf-8'))
    if manifest['source_commit'] != commit or 'v' + manifest['version'] != release:
        raise ValueError('Release provenance differs from the package manifest')
    state = bundled_state(source)
    output = Path(output)
    data = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'schema_version': 1, 'packages': []}
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported bundled history format')
    for package in state['packages']:
        descriptors = [d for d in state['descriptors'] if d['distribution'] == package['name']]
        for d in descriptors:
            if code_hash(d['entry_point'], source) != d['code_sha']:
                raise ValueError(f'Historical release source differs from its index: {d["id"]}')
        identity = {k: package[k] for k in ('version', 'sha256', 'code_sha')}
        identity['package'] = package['name']
        receipt = next((r for r in data['packages'] if r['implementation'] == identity), None)
        operators = {d['id']: d['version'] for d in descriptors}
        if receipt is None:
            receipt = {'implementation': identity, 'operators': operators, 'releases': []}
            data['packages'].append(receipt)
        elif receipt['operators'] != operators:
            raise ValueError('Conflicting historical operator versions')
        provenance = {'tag': release, 'commit': commit}
        if provenance not in receipt['releases']:
            receipt['releases'].append(provenance)
    output.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    return len(data['packages'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'biopipe/bundled_history.json')
    args = parser.parse_args()
    print(json.dumps({'package_receipts': record(args.source, args.release, args.commit, args.output)}))
