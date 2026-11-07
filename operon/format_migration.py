"""Propose SDK 3.7 declarations without importing implementation modules."""
import argparse
import ast
import json
import os
import pprint
from pathlib import Path
import uuid

from operon_sdk.declarations import source_declarations
from operon_sdk.format_inference import infer_legacy_formats
from operon_sdk.formats import DataFormats


def migrate(root, apply=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Source root must be an existing directory')
    proposals, reviews, writes = [], [], []
    for path in sorted(root.rglob('*.py')):
        if '__pycache__' in path.parts or path.is_symlink():
            continue
        try:
            original = path.read_bytes()
            source = original.decode('utf-8-sig')
            tree = ast.parse(source)
            candidates = [n for cls in tree.body if isinstance(cls, ast.ClassDef) for n in cls.body
                          if isinstance(n, (ast.Assign, ast.AnnAssign))
                          and any(isinstance(t, ast.Name) and t.id == 'definition'
                                  for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
            if not candidates:
                continue
            declarations = source_declarations(path, path.relative_to(root).with_suffix('').as_posix().replace('/', '.'))
            edits = []
            lines = source.encode('utf-8').splitlines(keepends=True)
            starts = [0]
            for line in lines:
                starts.append(starts[-1] + len(line))
            for declaration in declarations:
                name = declaration['entry_point'].split(':')[1]
                if declaration.get('protocol_revision') == '3.7':
                    continue
                result = infer_legacy_formats(declaration, source, name)
                if result['data_formats'] is not None:
                    formats = DataFormats.model_validate(result['data_formats'])
                    inputs = 0 if declaration['kind'] == 'reader' else (1 if declaration.get('inputs_arity') == '*' else declaration.get('inputs_arity', 0))
                    outputs = 1 if declaration['kind'] == 'reader' or declaration.get('output_parameter') else len(declaration.get('outputs', []))
                    if len(formats.inputs) != inputs or len(formats.outputs) != outputs:
                        result = {'data_formats': None, 'diagnostics': ['Proposed format arity differs from the existing declaration']}
                    else:
                        result['data_formats'] = formats.model_dump()
                record = {'path': str(path.relative_to(root)), 'id': declaration['id'], **result}
                if result['diagnostics']:
                    reviews.append(record)
                    continue
                cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
                assignment = next(n for n in cls.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                                  and any(isinstance(t, ast.Name) and t.id == 'definition'
                                          for t in (n.targets if isinstance(n, ast.Assign) else [n.target])))
                node = assignment.value
                fields = {'protocol_revision': '3.7', 'data_formats': result['data_formats']}
                missing = []
                indent = ' ' * (assignment.col_offset + 4)
                for field, value in fields.items():
                    rendered = pprint.pformat(value, width=90, sort_dicts=False).replace('\n', '\n' + indent)
                    previous = next((v for k, v in zip(node.keys, node.values) if ast.literal_eval(k) == field), None)
                    if previous is None:
                        missing.append(indent + repr(field) + ': ' + rendered + ',')
                    else:
                        edits.append((starts[previous.lineno-1]+previous.col_offset,
                                      starts[previous.end_lineno-1]+previous.end_col_offset, rendered.encode('utf-8')))
                if missing:
                    start = starts[node.lineno-1]+node.col_offset+1
                    suffix = '' if source.encode('utf-8')[start:start+1] in (b'\n', b'\r') else '\n' + indent
                    edits.append((start, start, ('\n' + '\n'.join(missing) + suffix).encode('utf-8')))
                proposals.append(record)
            updated = source.encode('utf-8')
            for start, end, replacement in sorted(edits, reverse=True):
                updated = updated[:start] + replacement + updated[end:]
            if edits:
                ast.parse(updated)
                writes.append((path, original, (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'') + updated))
        except (ValueError, SyntaxError, OSError, StopIteration, UnicodeError) as exc:
            reviews.append({'path': str(path.relative_to(root)), 'diagnostics': [str(exc)]})
    if apply:
        for path, original, _ in writes:
            if path.read_bytes() != original:
                raise ValueError(f'Source changed during inspection: {path}')
        for path, original, updated in writes:
            backup = path.with_name(path.name + '.pre-sdk37')
            if backup.exists():
                raise ValueError(f'Backup already exists: {backup}')
        staged, published = [], []
        try:
            for path, original, updated in writes:
                temporary = path.with_name(path.name + '.sdk37-' + uuid.uuid4().hex)
                temporary.write_bytes(updated)
                staged.append((path, original, temporary))
            for path, original, _ in staged:
                with path.with_name(path.name + '.pre-sdk37').open('xb') as backup:
                    backup.write(original)
            for path, original, temporary in staged:
                if path.read_bytes() != original:
                    raise ValueError(f'Source changed during publication: {path}')
                os.replace(temporary, path)
                published.append((path, original))
        except BaseException:
            for path, original in reversed(published):
                restore = path.with_name(path.name + '.sdk37-restore-' + uuid.uuid4().hex)
                restore.write_bytes(original)
                os.replace(restore, path)
            raise
        finally:
            for _, _, temporary in staged:
                temporary.unlink(missing_ok=True)
    return {'applied': apply, 'proposals': proposals, 'review_required': reviews,
            'changed_files': [str(p.relative_to(root)) for p, _, _ in writes]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = migrate(args.root, args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(2 if result['review_required'] else 0)
