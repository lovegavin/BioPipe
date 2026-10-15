"""Portable dependency declarations shared by scanning, packaging and startup."""
import ast
import re
from packaging.requirements import Requirement


def requirements(values):
    if not isinstance(values, list) or any(not isinstance(v, str) or '\n' in v or '\r' in v for v in values):
        raise ValueError('dependencies must be a list of PEP 508 requirement strings')
    result = []
    for value in values:
        requirement = Requirement(value)
        if requirement.url:
            raise ValueError('Dependency URLs and local paths are not supported; use package names and version ranges')
        result.append(str(requirement))
    return sorted(set(result))


def imports(values):
    if not isinstance(values, list) or any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', v) for v in values):
        raise ValueError('dependency_imports must contain Python module names')
    return sorted(set(values))


def declarations(cls, previous=None):
    result = {}
    for key, validate in (('dependencies', requirements), ('dependency_imports', imports)):
        value = getattr(cls, key, None)
        if value is None:
            value = (previous or {}).get(key)
        if value is not None:
            result[key] = validate(value)
    return result


def source_requirements(source):
    """Read literal metadata before importing code that needs the dependency."""
    tree = ast.parse(source)
    values = []
    for parent in [tree, *[n for n in tree.body if isinstance(n, ast.ClassDef)]]:
        for node in parent.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if isinstance(parent, ast.ClassDef) and target.id == 'dependencies':
                    value = ast.literal_eval(node.value)
                    if value is not None:
                        values.extend(requirements(value))
                elif parent is tree and target.id == 'BIOPIPE_PLUGIN':
                    values.extend(requirements(ast.literal_eval(node.value).get('dependencies', [])))
    return sorted(set(values))


def source_entries(source, module):
    """Literal per-class dependencies for direct SDK subclasses in a .py drop-in.

    Complex/dynamic modules retain the module entry-point fallback. Discovery
    still imports and validates the real classes in a disposable process.
    """
    tree = ast.parse(source)
    aliases = {'Step': 'operator', 'Operator': 'operator', 'Reader': 'reader'}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in ('biopipe_sdk', 'src.task.step.base', 'src.reader.base'):
            for alias in node.names:
                if alias.name in aliases:
                    aliases[alias.asname or alias.name] = aliases[alias.name]
    result = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        kinds = [aliases[b.id] for b in node.bases if isinstance(b, ast.Name) and b.id in aliases]
        if not kinds:
            return []  # Inheritance may hide another extension; use discovery.
        dependencies = []
        for field in node.body:
            targets = field.targets if isinstance(field, ast.Assign) else [field.target] if isinstance(field, ast.AnnAssign) else []
            if any(isinstance(t, ast.Name) and t.id == 'dependencies' for t in targets):
                value = ast.literal_eval(field.value)
                dependencies = requirements(value) if value is not None else []
        result.append({'entry': module + ':' + node.name, 'kind': kinds[0], 'dependencies': dependencies})
    return result
