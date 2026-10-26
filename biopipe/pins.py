"""Resolve graph pins without rewriting archived job evidence.

Installed wheels retain their executable generations. Old bundled entries only
retained metadata, so an identified bundled pin follows the installed source
with an explicit migration receipt. Unknown/wheel pins never get that fallback.
"""
from copy import deepcopy
import hashlib
import json


def identity(pin):
    return tuple(sorted(pin.items()))


def graphs(graph):
    yield graph
    for node in graph.nodes:
        if node.kind == 'route':
            yield from graphs(node.route.graph)


def requirements(graph, replacements=None):
    required = {}
    for part in graphs(graph):
        for key, original in part.plugin_lock.items():
            pin = (replacements or {}).get((key, identity(original)), original)
            if key in required and required[key] != pin:
                raise ValueError(f'Conflicting plugin versions in one graph: {key}')
            required[key] = pin
    return required


def matches(state, required):
    enabled = {p['name'] for p in state['packages'] if p.get('enabled', True)}
    available = {d['id']: d['implementation'] for d in state['descriptors'] if d['distribution'] in enabled}
    return all(available.get(key) == pin for key, pin in required.items())


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
    replacements = {}
    for state in candidates:
        for old in state['descriptors']:
            new = current.get(old['id'])
            if (old.get('origin') == 'bundled' and new and old['distribution'] == new['distribution']
                    and old.get('code_sha') != new.get('code_sha')):
                replacements[old['id'], identity(old['implementation'])] = new['implementation']
    required = requirements(graph, replacements)
    updates = {}
    for part in graphs(graph):
        for key, before in part.plugin_lock.items():
            after = replacements.get((key, identity(before)), before)
            if before != after:
                updates[key, identity(before)] = {'operator': key, 'before': before, 'after': after,
                    'reason': 'Bundled source was updated; historical registry retained metadata only'}
    for raw in candidates:
        candidate = refresh_bundled(raw, bundled)
        if matches(candidate, required):
            value = deepcopy(candidate)
            # Also report unrelated bundled entries replaced in a retained wheel
            # generation: workers must not import stale, unused builtin locks.
            live = {d['id']: d for d in candidate['descriptors']}
            for old in raw['descriptors']:
                new = live.get(old['id'])
                if old.get('origin') == 'bundled' and new and old['implementation'] != new['implementation']:
                    updates[old['id'], identity(old['implementation'])] = {'operator': old['id'],
                        'before': old['implementation'], 'after': new['implementation'],
                        'reason': 'Bundled source metadata refreshed in a retained plugin generation'}
            if updates:
                value['bundled_updates'] = list(updates.values())
            return value
    raise ValueError('Required plugin versions are unavailable; install the original packages. '
                     'Unknown or wheel pins are not automatically replaced.')
