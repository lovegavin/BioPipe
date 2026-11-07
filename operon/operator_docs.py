"""Progressive operator discovery, using registry metadata and immutable Markdown.

No operator modules or scientific libraries are imported by this service. API,
CLI, MCP and the desktop consume the same versioned descriptions.
"""
from copy import deepcopy
import json
from pathlib import Path
import re

from operon_sdk.documentation import sections as markdown_sections, verify_content


def _io_path(path):
    from operon.bytecode import filesystem_path
    return Path(filesystem_path(path, resolve=False))


def _markdown_path(root, descriptor):
    module = descriptor['entry_point'].split(':')[0].replace('.', '/')
    source = root / (module + '.py')
    if not _io_path(source).is_file():
        source = root / module / '__init__.py'
    return source.parent / descriptor['documentation']['path']


def document_bytes(manager, state, descriptor):
    metadata = descriptor.get('documentation')
    if not metadata:
        return None
    from operon_sdk.protocol import Documentation
    metadata = Documentation.model_validate(metadata).model_dump()
    cache = _io_path(manager.directory / 'documentation' / (metadata['sha256'] + '.md'))
    roots = [manager.directory / relative for relative in state.get('code_paths', [])]
    from operon.plugins import ROOT
    from operon.library_location import source_root
    roots.append(source_root() or ROOT)
    candidates = [cache, *[_io_path(_markdown_path(root, descriptor)) for root in roots]]
    for path in candidates:
        if path.is_file():
            content = path.read_bytes()
            try:
                verify_content(content, metadata)
            except (ValueError, UnicodeError):
                if path == cache:
                    raise
                continue
            return content
    raise ValueError(f"Documentation for this exact implementation is unavailable: {descriptor['id']} ({metadata['sha256']})")


def cache_document(manager, metadata, content):
    verify_content(content, metadata)
    path = _io_path(manager.directory / 'documentation' / (metadata['sha256'] + '.md'))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        verify_content(path.read_bytes(), metadata)
    else:
        # A content address is immutable. Atomic replacement cannot expose a
        # partial document to concurrent readers or an archived job.
        import os, uuid
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
        try:
            temporary.write_bytes(content)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def cache_state(manager, state):
    for descriptor in state['descriptors']:
        if descriptor.get('documentation'):
            cache_document(manager, descriptor['documentation'], document_bytes(manager, state, descriptor))


def cache_sources(manager, records, root):
    for descriptor in records:
        if descriptor.get('documentation'):
            content = _io_path(_markdown_path(Path(root), descriptor)).read_bytes()
            cache_document(manager, descriptor['documentation'], content)


def cache_wheel(manager, wheel):
    import zipfile
    from operon_sdk.documentation import archive_path
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read(next(name for name in names if name.endswith('.dist-info/operon.json'))))
        for descriptor in manifest['descriptors']:
            if descriptor.get('documentation'):
                cache_document(manager, descriptor['documentation'], archive.read(archive_path(names, descriptor)))


def parameter_markdown(descriptor):
    schema = descriptor['parameters_schema']
    lines = ['## Parameters', '', '| Name | Type | Required | Default | Description |', '| --- | --- | --- | --- | --- |']
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    for name, value in schema.get('properties', {}).items():
        lines.append('| ' + ' | '.join(map(cell, [name, value.get('type', 'any'),
                     name in schema.get('required', []), json.dumps(value['default'], ensure_ascii=False) if 'default' in value else '—',
                     value.get('description', value.get('title', ''))])) + ' |')
    lines.extend(['', 'Use the structured `parameters_schema` for exact ranges, choices and nested constraints.',
                  'Saved workflows keep their own frozen parameter values; changing defaults does not change them.'])
    return '\n'.join(lines)


class OperatorDocs:
    def __init__(self, manager):
        self.manager = manager
        self._index_cache = (None, [])

    def _state(self, generation=None):
        current = self.manager.state()
        if generation is None or generation == current['generation']:
            return current
        if not isinstance(generation, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', generation):
            raise ValueError('Invalid registry generation')
        for path in (self.manager.directory / 'snapshots' / (generation + '.json'),
                     self.manager.directory / 'environments' / generation / 'lock.json'):
            path = _io_path(path)
            if path.is_file():
                return json.loads(path.read_text(encoding='utf-8'))
        raise KeyError('Unknown registry generation')

    def search(self, query='', *, kind=None, category=None, limit=20, offset=0, view='full'):
        if view not in ('brief', 'full'):
            raise ValueError('view must be brief or full')
        if kind not in (None, 'operator', 'reader'):
            raise ValueError('kind must be operator or reader')
        if not isinstance(query, str) or len(query) > 1000:
            raise ValueError('query must be a string of at most 1000 characters')
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError('Use limit 1..100 and a non-negative offset')
        state = self._state()
        cached_generation, index = self._index_cache
        if state['generation'] != cached_generation:
            from operon.plugins import active_descriptors
            index = []
            for descriptor in active_descriptors(state):
                doc = descriptor.get('documentation') or {}
                item = {key: deepcopy(descriptor.get(key)) for key in ('id', 'kind', 'title', 'description', 'category', 'version')}
                item.update(summary=doc.get('summary') or descriptor.get('description', ''),
                            aliases=deepcopy(descriptor.get('title_aliases', [])),
                            documentation_available=bool(doc), documentation_status=doc.get('status', 'missing'),
                            sections=doc.get('sections', []),
                            implementation=deepcopy(descriptor.get('implementation', {})))
                index.append(item)
            index.sort(key=lambda item: item['id'])
            # Publish a complete generation in one assignment. Concurrent API
            # requests must never observe a half-built or mixed-generation index.
            self._index_cache = (state['generation'], index)
        terms = re.findall(r'[^\W_]+', query.casefold())
        def score(item):
            total = 0
            for term in terms:
                best = 0
                forms = {term, term[:-1]} if len(term) > 3 and term.endswith('s') else {term}
                for field, weight in (('id', 12), ('title', 10), ('aliases', 10),
                                      ('category', 4), ('summary', 2), ('description', 1)):
                    text = str(item.get(field) or '').casefold()
                    words = set(re.findall(r'[^\W_]+', text))
                    # Word matching avoids liability matching reliability; allow
                    # substrings for scripts that do not delimit words by spaces.
                    if forms & words or not term.isascii() and term in text:
                        best = max(best, weight)
                if not best:
                    return -1
                total += best
            if query.strip().casefold() == item['id'].casefold():
                total += 1000
            elif query.strip().casefold() == str(item.get('title', '')).casefold():
                total += 100
            return total
        ranked = [(score(item), item) for item in index
                  if (not kind or item['kind'] == kind) and (not category or item['category'] == category)]
        matches = [item for rank, item in sorted(ranked, key=lambda pair: (-pair[0], pair[1]['id'])) if rank >= 0]
        items = deepcopy(matches[offset:offset+limit])
        if view == 'brief':
            items = [{**{key: item[key] for key in ('id', 'kind', 'title', 'category', 'documentation_status')},
                      'summary': (item.get('summary') or '')[:240],
                      **({'summary_truncated': True} if len(item.get('summary') or '') > 240 else {})} for item in items]
        return {'items': items, 'total': len(matches), 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if offset + limit < len(matches) else None,
                'generation': state['generation']}

    def describe(self, ids, *, sections=None, generation=None, view='full'):
        if view not in ('schema', 'docs', 'full'):
            raise ValueError('view must be schema, docs or full')
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(not isinstance(i, str) for i in ids)):
            raise ValueError('Request 1..20 operator or Reader IDs')
        if sections is not None and (not isinstance(sections, list) or len(sections) > 30 or any(not isinstance(s, str) for s in sections)):
            raise ValueError('sections must be a list of at most 30 heading names')
        state = self._state(generation)
        from operon.plugins import active_descriptors
        available = {d['id']: d for d in active_descriptors(state)}
        items = []
        for key in ids:
            if key not in available:
                raise KeyError('Unknown or disabled operator: ' + key)
            descriptor = available[key]
            from operon_sdk.protocol import Descriptor
            spec = {k: deepcopy(v) for k, v in descriptor.items() if k in Descriptor.model_fields or k == 'implementation'}
            metadata = deepcopy(descriptor.get('documentation') or {})
            doc = {**metadata, 'available': bool(metadata), 'status': metadata.get('status', 'missing')}
            if sections:
                parts = {}
                if metadata and any(name not in ('parameters', 'contracts') for name in sections):
                    content = document_bytes(self.manager, state, descriptor)
                    text = verify_content(content, metadata)
                    parts = markdown_sections(text)
                parts['parameters'] = parameter_markdown(descriptor)
                parts['contracts'] = '## Contracts\n\n```json\n' + json.dumps(descriptor['contracts'], indent=2, ensure_ascii=False) + '\n```'
                requested = list(parts) if '*' in sections else sections
                missing = [name for name in requested if name not in parts]
                if missing:
                    raise ValueError('Unknown documentation sections: ' + ', '.join(missing))
                doc['content'] = {name: parts[name] for name in requested}
            doc['sections'] = list(dict.fromkeys([*metadata.get('sections', []), 'parameters', 'contracts']))
            if view != 'full':
                keys = {'id', 'kind', 'title', 'description', 'version'}
                if view == 'schema':
                    keys.update(('parameters_schema', 'contracts', 'resources', 'inputs_arity', 'outputs',
                                 'output_parameter', 'extensions', 'requires_siblings', 'excludes_siblings',
                                 'handles_compression', 'file_input'))
                spec = {key: value for key, value in spec.items() if key in keys}
                if view == 'schema':
                    from .platforms import supported_systems, systems_status
                    spec['supported_systems'] = supported_systems(descriptor)
                    spec['systems_status'] = systems_status(descriptor)
                doc = {key: value for key, value in doc.items() if key in
                       ('available', 'status', 'sections', 'sha256', 'content')}
            items.append({'descriptor': spec, 'documentation': doc})
        return {'items': items, 'generation': state['generation']}
