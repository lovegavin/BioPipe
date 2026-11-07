"""Conservative, import-free format proposals for legacy declarations."""
import ast


def _port_kind(rule):
    kind = rule.get('kind', 'form')
    kinds = kind if isinstance(kind, list) else [kind]
    if kinds and set(kinds) == {'form'}:
        return 'form'
    if kinds and set(kinds) == {'file'}:
        return 'file_artifact'
    return None


def _contract_container(rule, input_kinds=(), depth=0):
    """Read existing protocol guarantees, without loading scientific code."""
    if not isinstance(rule, dict) or depth > 4:
        return None
    if rule.get('kind') == 'file':
        return 'file_artifact'
    if rule.get('kind') == 'form' or rule.get('numeric') is True:
        return 'form'
    mode = rule.get('mode')
    if mode == 'declare':
        schema = rule.get('schema')
        return _port_kind(schema) if isinstance(schema, dict) else None
    if mode == 'choose':
        alternatives = list(rule.get('cases', {}).values()) + [rule.get('otherwise')]
        kinds = {_contract_container(item, input_kinds, depth + 1) for item in alternatives}
        return next(iter(kinds)) if len(kinds) == 1 else None
    inheriting = {'project', 'subset', 'select', 'drop', 'rename', 'transpose', 'transform',
                  'cox_regression', 'logrank_test', 'pca', 'regress', 'compare_groups',
                  'correction', 'attach', 'concat'}
    if mode in inheriting and input_kinds and input_kinds[0] == 'form':
        return 'form'
    return None


def _output_flow(tree, method, reader):
    known = {'Form': 'form', 'FileArtifact': 'file_artifact'}
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module == 'operon_sdk' or node.module == 'src.core' or (node.module or '').startswith('src.core.')):
            for name in node.names:
                if name.name in known:
                    aliases[name.asname or name.name] = known[name.name]
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for name in node.names:
                aliases.pop(name.asname or name.name.split('.')[0], None)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            aliases.pop(node.name, None)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    aliases.pop(target.id, None)
    helpers = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    helpers.pop(target.id, None)
    context = method.args.args[1].arg if not reader and len(method.args.args) > 1 else None
    unknown = {'?'}

    def evaluate(node, env, stack):
        if isinstance(node, ast.Name):
            return env.get(node.id, unknown)
        if isinstance(node, ast.IfExp):
            return evaluate(node.body, env, stack) | evaluate(node.orelse, env, stack)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            if name in aliases and name not in env:
                return {aliases[name]}
            if name in helpers and name not in env and name not in stack and len(stack) < 4:
                helper = helpers[name]
                arguments = {p.arg: evaluate(a, env, stack) for p, a in zip(helper.args.args, node.args)}
                returns, _, _, terminated = walk(helper.body, arguments, (*stack, name), None)
                return returns if terminated else returns | unknown
        return unknown

    def walk(statements, env, stack, ctx):
        env = dict(env)
        returns, writes = set(), set()
        terminated = False
        for node in statements:
            if isinstance(node, ast.Return):
                returns |= evaluate(node.value, env, stack)
                if ctx is not None and not writes:
                    writes |= unknown
                terminated = True
                break
            if isinstance(node, ast.Raise):
                terminated = True
                break
            if isinstance(node, (ast.Break, ast.Continue)):
                break
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                kinds = evaluate(node.value, env, stack)
                for target in targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = kinds
                    elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == ctx:
                        writes |= kinds
            elif isinstance(node, ast.If):
                lr, lw, le, lt = walk(node.body, env, stack, ctx)
                rr, rw, re, rt = walk(node.orelse, env, stack, ctx)
                returns |= lr | rr
                writes |= lw | rw
                env = {k: le.get(k, unknown) | re.get(k, unknown) for k in le.keys() | re.keys()}
                if lt and rt:
                    terminated = True
                    break
            elif isinstance(node, (ast.For, ast.While, ast.With, ast.Try)):
                branches = [node.body, getattr(node, 'orelse', []), getattr(node, 'finalbody', [])]
                branches += [h.body for h in getattr(node, 'handlers', [])]
                for branch in branches:
                    r, w, e, _ = walk(branch, env, stack, ctx)
                    returns |= r
                    writes |= w
                    if isinstance(node, (ast.For, ast.While)) and w:
                        writes |= unknown  # The loop may run zero times.
                    env = {k: env.get(k, unknown) | e.get(k, unknown) for k in env.keys() | e.keys()}
        return returns, writes, env, terminated

    returns, writes, _, terminated = walk(method.body, {}, (method.name,), context)
    return (returns if terminated else returns | unknown) if reader else writes


def infer_legacy_formats(declaration, source, class_name):
    """Return a proposal plus diagnostics; ambiguous outputs never become Form."""
    if declaration.get('data_formats') is not None:
        return {'data_formats': declaration['data_formats'], 'diagnostics': []}
    tree = ast.parse(source)
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name), None)
    if cls is None:
        return {'data_formats': None, 'diagnostics': ['Implementation class not found']}
    contracts = declaration.get('contracts', {})
    inputs = contracts.get('inputs', [])
    diagnostics = []
    def port(kind):
        return {'logical_type': kind, 'representations': [kind]}
    incoming = []
    for index, contract in enumerate(inputs):
        kind = _port_kind(contract)
        if kind is None:
            diagnostics.append(f'Input {index}: no unambiguous Form/file contract; review polymorphic capability')
        else:
            incoming.append(port(kind))
    output = contracts.get('output', {})
    no_outputs = not declaration.get('outputs') and not declaration.get('output_parameter')
    if output.get('mode') == 'report' or (declaration.get('kind') == 'operator' and no_outputs and output.get('mode') == 'none'):
        outgoing = []
    else:
        reader = declaration.get('kind') == 'reader'
        method = next((n for n in cls.body if isinstance(n, ast.FunctionDef)
                       and n.name == ('read' if reader else 'run')), None)
        evidence = _output_flow(tree, method, reader) if method else {'?'}
        declared = _port_kind(output) if reader else _contract_container(output, [item['logical_type'] for item in incoming])
        if declared and evidence <= {'?'}:
            evidence = {declared}
        elif declared and evidence - {'?', declared}:
            evidence = {'?'}  # A declaration contradicting observed flow needs review.
        if len(evidence) != 1 or '?' in evidence:
            diagnostics.append('Output requires review: no unique Form/FileArtifact evidence in read/run')
            outgoing = []
        else:
            kind = next(iter(evidence))
            count = 1 if declaration.get('kind') == 'reader' or declaration.get('output_parameter') else len(declaration.get('outputs', []))
            if not count:
                diagnostics.append('Output arity is not declared')
            outgoing = [port(kind) for _ in range(count)]
    return {'data_formats': None if diagnostics else {'inputs': incoming, 'outputs': outgoing},
            'diagnostics': diagnostics}
