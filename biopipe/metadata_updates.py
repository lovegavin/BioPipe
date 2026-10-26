"""Declaration-only transactions reuse code paths and dependency targets."""
from copy import deepcopy

# Changing these requires the installation/hook-validation transaction.
EXECUTION_KEYS = ('id', 'kind', 'entry_point', 'code_sha', 'dependencies', 'dependency_imports', 'resources')


def replace_declarations(state, declarations):
    from biopipe_sdk.declarations import declaration_hash
    from biopipe_sdk.protocol import Descriptor, validate_declaration
    result = deepcopy(state)
    existing = {d['id']: d for d in result['descriptors']}
    seen = set()
    for incoming in declarations:
        if incoming['id'] in seen:
            raise ValueError('Duplicate declaration ID: ' + incoming['id'])
        seen.add(incoming['id'])
        old = existing.get(incoming['id'])
        if old is None:
            raise ValueError('New operators require installation: ' + incoming['id'])
        new = {k: deepcopy(v) for k, v in incoming.items() if k in Descriptor.model_fields}
        for key in EXECUTION_KEYS:
            if new.get(key, []) != old.get(key, []):
                raise ValueError(f'{incoming["id"]}: {key} changed; refresh/install the provider code')
        new['declaration_sha'] = '0' * 64
        new = Descriptor.model_validate(new).model_dump(exclude_unset=True)
        new['declaration_sha'] = declaration_hash(new)
        validate_declaration(new)
        from pathlib import Path
        from biopipe_sdk.declarations import implementation_root
        from biopipe_sdk.drift import check_source
        relative = new['entry_point'].split(':')[0].replace('.', '/')
        roots = [Path(state['_runtime_root']) / p for p in state.get('code_paths', [])]
        try:
            roots.append(implementation_root(new['entry_point']))
        except ValueError:
            pass
        source = next((p for root in roots for p in (root / (relative + '.py'), root / relative / '__init__.py') if p.is_file()), None)
        if source is None:
            raise ValueError('Cannot validate installed implementation: ' + new['id'])
        errors, warnings = check_source(source.read_text(encoding='utf-8'), new)
        if errors:
            raise ValueError('; '.join(errors))
        for key in Descriptor.model_fields:
            old.pop(key, None)
        old.update(new)
        old['implementation']['declaration_sha'] = new['declaration_sha']
    return result
