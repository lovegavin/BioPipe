"""Static, conservative checks between implementation reads and declarations."""
import ast

ENGINE_PARAMETERS = {'output', '_input_names'}


def check_source(text, descriptor):
    from .declarations import DECLARATION_ATTRIBUTES
    tree = ast.parse(text)
    classname = descriptor['entry_point'].split(':')[1]
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == classname), None)
    if cls is None:
        return [f'Missing implementation class: {classname}'], []
    errors, warnings, keys = [], [], set()
    for node in cls.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
            if names & DECLARATION_ATTRIBUTES:
                errors.append(f'Use definition + a separate parameter JSON: {sorted(names & DECLARATION_ATTRIBUTES)}')
    for fn in [n for n in ast.walk(cls) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        aliases = {'params'} if any(a.arg == 'params' for a in fn.args.args) else set()
        if descriptor['kind'] == 'reader' and fn.args.kwarg:
            aliases.add(fn.args.kwarg.arg)
        def is_params(value):
            return (isinstance(value, ast.Attribute) and value.attr == 'step_params'
                    or isinstance(value, ast.Name) and value.id in aliases
                    or isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id in {'dict', 'deepcopy'} and value.args and is_params(value.args[0]))
        # Resolve aliases to a fixed point (p = ctx.step_params; options = p).
        for _ in range(len(fn.body) + 1):
            before = set(aliases)
            for node in ast.walk(fn):
                if isinstance(node, ast.Assign) and is_params(node.value):
                    aliases.update(t.id for t in node.targets if isinstance(t, ast.Name))
            if aliases == before:
                break
        for node in ast.walk(fn):
            key = None
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and is_params(node.value):
                key = node.slice
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in {'get', 'pop', 'setdefault'} and is_params(node.func.value) and node.args):
                key = node.args[0]
            if key is not None:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
                else:
                    warnings.append(f'{fn.name}:{node.lineno}: dynamic parameter key needs a fixture test')
    declared = set(descriptor['parameters_schema'].get('properties', {}))
    unknown = keys - declared - ENGINE_PARAMETERS
    if unknown:
        errors.append(f'Undeclared parameter reads: {sorted(unknown)}')
    unused = declared - keys - ENGINE_PARAMETERS
    if unused:
        warnings.append(f'No direct parameter read (may be forwarded to a helper): {sorted(unused)}')
    def references(value):
        if isinstance(value, dict):
            if isinstance(value.get('param'), str):
                yield value['param']
            for child in value.values():
                yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)
    missing = set(references(descriptor['contracts'])) - declared - ENGINE_PARAMETERS
    if missing:
        errors.append(f'Undeclared contract parameters: {sorted(missing)}')
    return errors, warnings
