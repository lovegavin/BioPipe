"""Static route templates must not capture the builder's filesystem or paths."""
import json
from pathlib import Path, PureWindowsPath
import shutil

from operon.packages import bundled_state
from operon.registry import build_routes
from src.web.operator_catalog import catalog_from_descriptors


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_route_graphs_are_identical_across_build_roots(tmp_path):
    catalog = catalog_from_descriptors(bundled_state(manifest_only=True)['descriptors'])
    previous = json.loads((ROOT / 'library/seed/src/web/builtin_routes.json').read_text(encoding='utf-8'))
    operators = {item['id']: item for item in catalog['operators']}
    results = []
    for name in ('first-installation', 'relocated-installation'):
        root = tmp_path / name
        shutil.copytree(ROOT / 'library/seed/routes', root / 'routes')
        if not results:
            # Whether a template's input happens to exist must not affect its
            # published path. Its payload deliberately is not valid CSV.
            existing = root / '.studio/builtin-inputs/gwas/input/phenotype.csv'
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b'not parsed by registry maintenance')
        built, errors = build_routes(root, catalog, previous)
        assert not errors
        assert len(built['routes']) == len(previous['routes'])
        text = json.dumps(built)
        assert root.as_posix() not in text and str(root) not in text
        for route in built['routes']:
            graph = route['graph']
            paths = [graph['base_dir']]
            for node in graph['nodes']:
                if node['kind'] == 'source':
                    paths.append(node['source']['path'])
                elif node['kind'] == 'operator':
                    fields = operators[node['operator']]['parameters_schema'].get('properties', {})
                    paths.extend(node['params'][key] for key, field in fields.items()
                                 if field.get('x-operon-path') == 'workflow' and node['params'].get(key))
            assert all(not Path(path).is_absolute() and not PureWindowsPath(path).is_absolute()
                       for path in paths), (route['name'], paths)
        results.append(built)
    assert results[0] == results[1]
    repeated, errors = build_routes(root, catalog, results[0])
    assert not errors and repeated == results[0]
