"""Generate/check Markdown companions using AST + JSON only.

Authored pages are never overwritten. Generated pages are marked explicitly and
must not be mistaken for independently reviewed scientific documentation.
"""
import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def render(source, cls, declaration, module_doc=None):
    name = declaration['id']
    notes = list(dict.fromkeys(note.strip() for note in [module_doc, ast.get_docstring(cls)] if note and note.strip()))
    purpose = '\n\n'.join(notes) or declaration.get('description') or f"Apply the `{name}` {declaration['kind']}."
    # Source docstrings may already contain headings with the same names as
    # the generated reference. Quote them so the public section IDs stay unique.
    purpose = '\n'.join('> ' + line if line else '>' for line in purpose.splitlines())
    count = declaration.get('inputs_arity', 0)
    memory = ', '.join(declaration.get('resources', {}).get('memory_modes', ['full']))
    environment = declaration.get('resources', {}).get('environment')
    environment = ('This operator executes in the dedicated `' + environment + '` interpreter; see docs/large_resources.md for resolution and overrides.'
                   if environment else 'Runs in the shared BioPipe interpreter.')
    return f'''<!-- biopipe:generated -->
# {declaration.get('title') or name}

## Purpose

{purpose}

## Inputs and outputs

Kind: `{declaration['kind']}`. Operator ID: `{name}`.
{'This Reader opens files with extensions: ' + ', '.join('`' + e + '`' for e in declaration.get('extensions', [])) + '.' if declaration['kind'] == 'reader' else 'Input count: `' + str(count) + '`.'}
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

{environment}

## Limitations

Declared memory modes: {memory}. BioPipe retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `{source}` (`{cls.name}`).
'''


def build(root, *, check=False):
    from biopipe_sdk.declarations import source_declarations
    from biopipe_sdk.documentation import relative_path
    from biopipe.library_location import source_root
    root = source_root(root)
    changed, preserved, pages, errors = [], [], [], []
    indexes = {'operator': [], 'reader': []}
    for folder in ('src/task/step/steps', 'src/reader/readers'):
        for path in sorted((root / folder).glob('[!_]*.py')):
            relative = path.relative_to(root).as_posix()
            try:
                records = source_declarations(path, relative[:-3].replace('/', '.'))
                tree = ast.parse(path.read_text(encoding='utf-8'))
                classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
                for descriptor in records:
                    cls = classes[descriptor['entry_point'].split(':')[1]]
                    metadata = descriptor.get('documentation') or {}
                    if isinstance(metadata, str):
                        metadata = {'path': metadata}
                    relative_document = relative_path(metadata.get('path', path.stem + '.' + cls.name + '.md'))
                    destination = (path.parent / relative_document).resolve()
                    if not destination.is_relative_to(path.parent.resolve()):
                        raise ValueError('Documentation must remain inside the implementation directory')
                    text = render(relative, cls, descriptor, ast.get_docstring(tree))
                    existing_bytes = None
                    if destination.exists():
                        existing_bytes = destination.read_bytes()
                        existing = destination.read_text(encoding='utf-8')
                        if '<!-- biopipe:generated -->' not in existing:
                            preserved.append(destination.relative_to(root).as_posix())
                            text = existing
                    else:
                        existing = None
                    generated = '<!-- biopipe:generated -->' in text
                    if existing != text or generated and existing_bytes != text.encode('utf-8'):
                        changed.append(destination.relative_to(root).as_posix())
                        if not check:
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            destination.write_text(text, encoding='utf-8', newline='\n')
                    pages.append(descriptor['id'])
                    indexes[descriptor['kind']].append({
                        'id': descriptor['id'], 'kind': descriptor['kind'],
                        'title': descriptor.get('title', descriptor['id']),
                        'category': descriptor.get('category'), 'version': descriptor['version'],
                        'description': descriptor.get('description', ''),
                        'doc': destination.relative_to(root).as_posix(),
                        'status': 'generated' if '<!-- biopipe:generated -->' in text else 'authored'})
            except (OSError, ValueError, KeyError, SyntaxError) as error:
                errors.append({'source': relative, 'error': str(error)})
    for kind, entries in indexes.items():
        destination = root / (kind + '_index.json')
        text = json.dumps(sorted(entries, key=lambda entry: entry['id']), indent=2, ensure_ascii=False) + '\n'
        if not destination.is_file() or destination.read_text(encoding='utf-8') != text:
            changed.append(destination.relative_to(root).as_posix())
            if not check:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(text, encoding='utf-8', newline='\n')
    return {'pages': len(pages), 'changed': changed, 'authored_preserved': preserved, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build(args.source_root.resolve(), check=args.check)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if result['errors'] or args.check and result['changed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
