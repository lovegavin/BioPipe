"""Keyed document diffs and conditional compensation, independent of transports."""
from copy import deepcopy
import json


def changes(before, after, path=()):
    """JSON differences; node/edge lists use stable IDs rather than fragile offsets."""
    result = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(before.keys() | after.keys()):
            if key in before and key in after:
                result.extend(changes(before[key], after[key], (*path, key)))
            else:
                result.append({'path': [*path, key], 'before_exists': key in before,
                               'after_exists': key in after, 'before': deepcopy(before.get(key)),
                               'after': deepcopy(after.get(key))})
    elif path and path[-1] in ('nodes', 'edges') and isinstance(before, list) and isinstance(after, list):
        old, new = {x['id']: x for x in before}, {x['id']: x for x in after}
        # Creation order breaks scientific execution ties. An explicit reorder
        # is one guarded list edit, rather than an invisible/no-op transaction.
        if [x['id'] for x in before if x['id'] in new] != [x['id'] for x in after if x['id'] in old]:
            return [{'path': list(path), 'before_exists': True, 'after_exists': True,
                     'before': deepcopy(before), 'after': deepcopy(after)}]
        for key in sorted(old.keys() | new.keys()):
            if key in old and key in new:
                result.extend(changes(old[key], new[key], (*path, key)))
            else:
                result.append({'path': [*path, key], 'before_exists': key in old,
                               'after_exists': key in new, 'before': deepcopy(old.get(key)),
                               'after': deepcopy(new.get(key)),
                               'before_index': next((i for i, x in enumerate(before) if x['id'] == key), None),
                               'after_index': next((i for i, x in enumerate(after) if x['id'] == key), None)})
    elif before != after:
        result.append({'path': list(path), 'before_exists': True, 'after_exists': True,
                       'before': deepcopy(before), 'after': deepcopy(after)})
    return result


def _lookup(container, key):
    if isinstance(container, list):
        return next(((True, x) for x in container if isinstance(x, dict) and x.get('id') == key), (False, None))
    if isinstance(container, dict):
        return key in container, container.get(key)
    return False, None


def compensate(graph, delta, *, redo=False):
    """Refuse overlapping edits; preserve unrelated edits since the transaction."""
    result = deepcopy(graph)
    expected, target = ('before', 'after') if redo else ('after', 'before')
    conflicts = []
    for change in delta:
        parent = result
        valid = True
        for key in change['path'][:-1]:
            exists, parent = _lookup(parent, key)
            if not exists:
                valid = False
                break
        key = change['path'][-1]
        exists, value = _lookup(parent, key) if valid else (False, None)
        if not valid or exists != change[expected + '_exists'] or (exists and value != change[expected]):
            conflicts.append(change['path'])
            continue
        if isinstance(parent, list):
            index = next((i for i, x in enumerate(parent) if x['id'] == key), len(parent))
            if exists:
                parent.pop(index)
            if change[target + '_exists']:
                position = change.get(target + '_index')
                parent.insert(min(position if position is not None else index, len(parent)), deepcopy(change[target]))
        elif change[target + '_exists']:
            parent[key] = deepcopy(change[target])
        else:
            parent.pop(key, None)
    return result, conflicts


def preview(change, maximum=600):
    result = {k: deepcopy(v) for k, v in change.items() if k not in ('before', 'after')}
    for key in ('before', 'after'):
        value = json.dumps(change[key], ensure_ascii=False, separators=(',', ':'))
        result[key] = value[:maximum]
        result[key + '_truncated'] = len(value) > maximum
    return result
