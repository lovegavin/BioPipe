"""Resolve graph pins without rewriting archived job evidence.

Installed wheels retain their executable generations. Old bundled entries only
retained metadata, so an identified bundled pin follows the installed source
within the same version with an explicit migration receipt. Declaration-only
changes do not require history; unknown code/wheel artifacts never get a fallback.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path


PIN_KEYS = ('version', 'package', 'sha256', 'code_sha')


def identity(pin, *, bundled=False):
    # A bundled sha256 fingerprints the *index and code*, so even a default-only
    # rebuild changes it. V3 code_sha identifies its executable bytes instead.
    # Wheels still require their exact artifact digest (native code/assets too).
    keys = PIN_KEYS
    if bundled and pin.get('code_sha'):
        keys = tuple(key for key in keys if key != 'sha256')
    return tuple((key, pin.get(key)) for key in keys)


@lru_cache(maxsize=1)
def _released_pins(path, stamp):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version') != 1:
        raise ValueError('Unsupported bundled compatibility receipt format')
    return {(key, identity(package['implementation'])): version
            for package in data['packages'] for key, version in package['operators'].items()}


def released_replacements(graph, current):
    """Recognize exact shipped artifacts, never infer trust from an ID alone."""
    path = Path(__file__).with_name('bundled_history.json')
    if not path.is_file():
        return {}
    stat = path.stat()
    receipts = _released_pins(str(path), (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
    result = {}
    for part in graphs(graph):
        for key, pin in part.plugin_lock.items():
            new = current.get(key)
            if (new and new.get('origin') == 'bundled' and
                    receipts.get((key, identity(pin))) == new.get('version') and
                    pin.get('package') == new['distribution'] and
                    pin.get('version') == new['implementation'].get('version')):
                result[key, identity(pin)] = new['implementation']
    return result


def graphs(graph):
    yield graph
    for node in graph.nodes:
        if node.kind == 'route':
            yield from graphs(node.route.graph)


def requirements(graph, replacements=None, *, state=None):
    required = {}
    bundled = {d['id'] for d in (state or {}).get('descriptors', []) if d.get('origin') == 'bundled'}
    for part in graphs(graph):
        for key, original in part.plugin_lock.items():
            pin = (replacements or {}).get((key, identity(original)), original)
            if (key in required and identity(required[key], bundled=key in bundled) !=
                    identity(pin, bundled=key in bundled)):
                raise ValueError(f'Conflicting plugin versions in one graph: {key}')
            required[key] = pin
    return required


def matches(state, required):
    enabled = {p['name'] for p in state['packages'] if p.get('enabled', True)}
    available = {d['id']: d for d in state['descriptors'] if d['distribution'] in enabled}
    return all(key in available and
               identity(available[key]['implementation'], bundled=available[key].get('origin') == 'bundled') ==
               identity(pin, bundled=available[key].get('origin') == 'bundled')
               for key, pin in required.items())


def refresh_bundled(candidate, bundled):
    """Replace metadata-only bundled entries, leaving wheel code/targets intact."""
    current = {p['name']: p for p in bundled['packages']}
    changed = {p['name'] for p in candidate['packages'] if p.get('origin') == 'bundled'
               and p['name'] in current and p.get('code_sha') != current[p['name']].get('code_sha')}
    if not changed:
        return candidate
    value = deepcopy(candidate)
    value['packages'] = [{**deepcopy(current[p['name']]), 'enabled': p.get('enabled', True)}
                         if p['name'] in changed and p.get('origin') == 'bundled' else p
                         for p in value['packages']]
    value['descriptors'] = [d for d in value['descriptors'] if not (d.get('origin') == 'bundled' and d['distribution'] in changed)]
    value['descriptors'].extend(deepcopy(d) for d in bundled['descriptors'] if d['distribution'] in changed)
    digest = hashlib.sha256(json.dumps(value['packages'], sort_keys=True).encode()).hexdigest()[:12]
    value['generation'] = candidate['generation'] + '-bundled-' + digest
    return value


def resolve(graph, candidates, bundled):
    current = {d['id']: d for d in bundled['descriptors']}
    released = released_replacements(graph, current)
    replacements = dict(released)
    for state in candidates:
        for old in state['descriptors']:
            new = current.get(old['id'])
            if (old.get('origin') == 'bundled' and new and old['distribution'] == new['distribution']
                    and old.get('version') == new.get('version')
                    and old['implementation'].get('version') == new['implementation'].get('version')
                    and old.get('code_sha') != new.get('code_sha')):
                replacements[old['id'], identity(old['implementation'])] = new['implementation']
    updates = {}
    for part in graphs(graph):
        for key, before in part.plugin_lock.items():
            after = replacements.get((key, identity(before)), before)
            if identity(before, bundled=True) != identity(after, bundled=True):
                updates[key, identity(before)] = {'operator': key, 'before': before, 'after': after,
                    'reason': ('Known released bundled implementation updated using its compatibility receipt'
                               if (key, identity(before)) in released else
                               'Bundled source was updated; historical registry retained metadata only')}
    conflict = None
    for raw in candidates:
        candidate = refresh_bundled(raw, bundled)
        try:
            required = requirements(graph, replacements, state=candidate)
        except ValueError as error:
            conflict = error
            continue
        if matches(candidate, required):
            value = deepcopy(candidate)
            # Also report unrelated bundled entries replaced in a retained wheel
            # generation: workers must not import stale, unused builtin locks.
            live = {d['id']: d for d in candidate['descriptors']}
            for old in raw['descriptors']:
                new = live.get(old['id'])
                if (old.get('origin') == 'bundled' and new and
                        identity(old['implementation'], bundled=True) != identity(new['implementation'], bundled=True)):
                    updates[old['id'], identity(old['implementation'])] = {'operator': old['id'],
                        'before': old['implementation'], 'after': new['implementation'],
                        'reason': 'Bundled source metadata refreshed in a retained plugin generation'}
            if updates:
                value['bundled_updates'] = list(updates.values())
            return value
    if conflict is not None:
        raise conflict
    raise ValueError('Required plugin versions are unavailable; install the original packages. '
                     'Unknown or wheel pins are not automatically replaced.')
