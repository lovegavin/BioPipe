"""Portable dependency declarations shared by scanning, packaging and startup."""
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
