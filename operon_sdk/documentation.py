"""Static, content-addressed Markdown resources for protocol v3 extensions.

Documentation is data, never imported or executed. The execution descriptor
contains only a compact index; full text is loaded explicitly by its hash.
"""
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re


def canonical_content(content):
    """Fingerprint UTF-8 Markdown consistently across Git/OS newline policies."""
    return content.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')


def relative_path(value):
    if not isinstance(value, str):
        raise ValueError('documentation.path must be a relative Markdown path')
    value = value.replace('\\', '/')
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or ':' in value or
            any(part in ('', '.', '..') for part in value.split('/')) or path.suffix.lower() != '.md'):
        raise ValueError('documentation.path must remain inside the implementation directory and end in .md')
    return value


def sections(markdown):
    """Return stable heading slugs and text; ignore headings inside code fences."""
    result, current, lines, fence = {}, 'overview', [], None
    for line in markdown.splitlines():
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            char = marker.group(1)[0]
            if fence is None:
                fence = char
            elif fence == char:
                fence = None
        match = None if fence else re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if match:
            if lines:
                result[current] = '\n'.join(lines).strip()
            current = re.sub(r'[^\w]+', '-', match.group(1).casefold()).strip('-') or 'section'
            if current in result:
                raise ValueError('Documentation headings must have unique names: ' + current)
            lines = [line]
        else:
            lines.append(line)
    if lines:
        result[current] = '\n'.join(lines).strip()
    return {key: value for key, value in result.items() if value}


def compile_documentation(source, declaration):
    value = declaration or {}
    if isinstance(value, str):
        value = {'path': value}
    relative = relative_path(value.get('path'))
    source = Path(source)
    path = (source.parent / relative).resolve()
    if not path.is_relative_to(source.parent.resolve()):
        raise ValueError('Documentation must remain inside the implementation directory')
    content = canonical_content(path.read_bytes())
    markdown = content.decode('utf-8')
    parts = sections(markdown)
    if '<!-- operon:generated -->' in markdown and value.get('status') == 'reviewed':
        raise ValueError('Generated documentation cannot claim reviewed status; provide an authored review first')
    paragraphs = [' '.join(line.strip().lstrip('> ').strip() for line in block.splitlines())
                  for block in re.split(r'\n\s*\n', markdown)
                  if block.strip() and not block.lstrip().startswith(('#', '<!--', '```', '|'))]
    return {'path': relative, 'sha256': sha256(content).hexdigest(),
            'summary': str(value.get('summary') or (paragraphs[0] if paragraphs else ''))[:500],
            'sections': list(parts), 'status': value.get('status', 'generated' if '<!-- operon:generated -->' in markdown else 'authored'),
            'minimum_sdk': '3.1.0'}


def archive_path(entries, descriptor):
    module = descriptor['entry_point'].split(':')[0].replace('.', '/')
    entry = module + '.py' if module + '.py' in entries else module + '/__init__.py'
    return str(PurePosixPath(entry).parent / relative_path(descriptor['documentation']['path']))


def verify_content(content, metadata):
    canonical = canonical_content(content)
    # Historical descriptors hashed raw Markdown bytes. Keep those immutable
    # resources valid; new descriptors use UTF-8/LF without changing code pins.
    if metadata['sha256'] not in (sha256(content).hexdigest(), sha256(canonical).hexdigest()):
        raise ValueError('Documentation content hash mismatch: ' + metadata['path'])
    text = canonical.decode('utf-8')
    if list(sections(text)) != metadata['sections']:
        raise ValueError('Documentation section index differs from Markdown')
    return text
