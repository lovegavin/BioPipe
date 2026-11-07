"""Public YAML project archives for the desktop's ordinary import/export flow."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

import yaml

from .workflow_spec import compile_spec, export_workflow, parse

FILES = {'workflow.yaml', 'parameters.json', 'execution.json', 'workflow.lock.json', 'ui.json'}


def export_archive(graph, staging):
    with TemporaryDirectory(dir=staging, prefix='yaml-') as temporary:
        export_workflow(graph, temporary)
        path = Path(temporary) / 'workflow.yaml'
        spec = parse(path.read_text(encoding='utf-8'))
        # A browser download has no known destination directory. Preserve the
        # graph's declared input paths; never publish staging-directory paths.
        for node in graph.nodes:
            if node.kind == 'source':
                data_path = node.source.path
                if data_path and (not node.source.location or node.source.location.kind != 'ssh'):
                    declared = Path(graph.base_dir) / data_path
                    data_path = str(declared.resolve()) if declared.is_absolute() else declared.as_posix()
                spec['sources'][node.id]['path'] = data_path
        path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding='utf-8')
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for name in sorted(FILES):
                archive.writestr(name, (Path(temporary) / name).read_bytes())
        return output.getvalue()


def is_workflow_archive(data):
    try:
        with ZipFile(BytesIO(data)) as archive:
            return 'workflow.yaml' in archive.namelist()
    except BadZipFile as exc:
        raise ValueError('Invalid workflow archive') from exc


def import_archive(data, staging, input_base):
    try:
        return _import_archive(data, staging, input_base)
    except (BadZipFile, RuntimeError, KeyError) as exc:
        raise ValueError('Cannot read workflow archive: ' + str(exc)) from exc


def _import_archive(data, staging, input_base):
    with ZipFile(BytesIO(data)) as archive, TemporaryDirectory(dir=staging, prefix='yaml-') as temporary:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != FILES:
            raise ValueError('A public workflow archive must contain exactly its five project files')
        for name in names:
            (Path(temporary) / name).write_bytes(archive.read(name))
        spec = parse((Path(temporary) / 'workflow.yaml').read_text(encoding='utf-8'))
        graph = compile_spec(spec, temporary)
        # Sidecars resolve in the archive; data resolves in the chosen project.
        for node in graph['nodes']:
            if node['kind'] == 'source' and (node['source'].get('location') or {}).get('kind') != 'ssh':
                node['source']['path'] = str((Path(input_base) / spec['sources'][node['id']]['path']).resolve())
        graph['base_dir'] = str(Path(input_base).resolve())
        return graph
