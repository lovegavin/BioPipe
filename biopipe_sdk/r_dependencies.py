"""Optional R requirements in the existing v3 resources object (pure data)."""
import re
from packaging.specifiers import SpecifierSet


def validate_r(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {'version', 'packages', 'bioconductor'}:
        raise ValueError('resources.r allows version, packages and bioconductor only')
    version = value.get('version', '>=4.3,<5')
    if not isinstance(version, str) or not version:
        raise ValueError('R version must be a version constraint')
    SpecifierSet(version)
    release = value.get('bioconductor')
    if release is not None and (not isinstance(release, str) or not re.fullmatch(r'3\.\d+', release)):
        raise ValueError('bioconductor must be a release such as 3.20')
    packages, seen = [], set()
    if not isinstance(value.get('packages', []), list):
        raise ValueError('R packages must be a list')
    for item in value.get('packages', []):
        if not isinstance(item, dict) or set(item) - {'name', 'source', 'version'}:
            raise ValueError('R package requires name, source and optional version')
        name, source, constraint = item.get('name'), item.get('source'), item.get('version', '')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9.]*', name) or name in seen:
            raise ValueError('Invalid or duplicate R package name')
        if source not in {'cran', 'bioconductor'} or not isinstance(constraint, str):
            raise ValueError('R source must be cran or bioconductor; version must be text')
        SpecifierSet(constraint)
        seen.add(name)
        packages.append({'name': name, 'source': source, 'version': constraint})
    if 'jsonlite' not in seen:
        packages.append({'name': 'jsonlite', 'source': 'cran', 'version': '>=1.8'})
    return {'version': version, 'packages': sorted(packages, key=lambda p: p['name']),
            **({'bioconductor': release} if release else {})}
