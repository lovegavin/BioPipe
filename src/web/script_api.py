"""Source inspection for the editor. No provider or uploaded code is executed."""
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict


class InspectScript(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str
    code: str
    script: dict | None = None


class ExtractScript(BaseModel):
    model_config = ConfigDict(extra='forbid')
    script: dict
    names: list[str]


class PublishScript(BaseModel):
    model_config = ConfigDict(extra='forbid')
    script: dict
    operator_id: str
    title: str
    category: str = 'data'
    version: str = '0.1.0'


def source_for(manager, identifier):
    state = manager.state()
    descriptor = next((d for d in state['descriptors'] if d['id'] == identifier), None)
    if descriptor is None:
        raise HTTPException(404, 'Unknown operator')
    module = descriptor['entry_point'].split(':')[0]
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*', module):
        return {'available': False, 'reason': 'Source module is not a Python module path'}
    roots = []
    directory = manager.directory.resolve()
    for relative in state.get('code_paths', []):
        root = (directory / relative).resolve()
        if root.is_relative_to(directory):
            roots.append(root)
    from operon.library_location import source_root
    seed = source_root()
    if seed:
        roots.append(seed.resolve())
    from operon_sdk.declarations import code_hash
    for root in roots:
        for relative in (module.replace('.', '/') + '.py', module.replace('.', '/') + '/__init__.py'):
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                continue
            if descriptor.get('code_sha') != code_hash(descriptor['entry_point'], root):
                continue
            return {'available': True, 'code': path.read_text(encoding='utf-8-sig'),
                    'filename': path.name, 'editable': False}
    return {'available': False, 'reason': 'Source for this exact registered implementation is unavailable'}


def mount_scripts(app, service):
    @app.post('/api/scripts/inspect')
    def inspect(payload: InspectScript):
        from operon.script_operators import inspect_source, validate_script, parameter_candidates
        if Path(payload.filename).name != payload.filename or '/' in payload.filename or '\\' in payload.filename:
            raise HTTPException(422, 'Script filename must be a basename')
        try:
            snapshot = inspect_source(payload.filename, payload.code)
            if payload.script is not None:
                previous = validate_script(payload.script)
                if previous['language'] != snapshot['language']:
                    raise ValueError('Changing language requires creating a new script operator')
                snapshot['parameters_schema'] = previous['parameters_schema']
                snapshot = validate_script(snapshot)
            return {'script': snapshot, 'candidates': parameter_candidates(snapshot['code'])
                    if snapshot['language'] == 'python' else []}
        except (ValueError, SyntaxError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post('/api/scripts/extract')
    def extract(payload: ExtractScript):
        from operon.script_operators import extract_parameters
        try:
            return extract_parameters(payload.script, payload.names)
        except (ValueError, SyntaxError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get('/api/operators/{identifier}/source')
    def source(identifier: str):
        return source_for(service.plugins, identifier)

    @app.post('/api/scripts/publish')
    def publish(payload: PublishScript):
        from operon.script_operators import export_script_package
        from operon.dropins import single_file_wheel
        directory = service.directory / 'script-inspection'
        directory.mkdir(parents=True, exist_ok=True)
        try:
            state = service.plugins.state()
            if any(d['id'] == payload.operator_id for d in state['descriptors']):
                raise ValueError('This operator ID already exists; choose a distinct ID for this saved script')
            with TemporaryDirectory(dir=directory) as folder:
                project = export_script_package(payload.script, folder, operator_id=payload.operator_id,
                                                title=payload.title, category=payload.category, version=payload.version)
                source = Path(folder) / project['module'] / '__init__.py'
                metadata = {'name': project['package'], 'version': project['version'],
                            'dependencies': ['operon-studio>=3.0.0,<4']}
                source.write_text('OPERON_PLUGIN = ' + repr(metadata) + '\n' + source.read_text(encoding='utf-8'), encoding='utf-8')
                wheel = single_file_wheel(source, Path(folder) / 'dist')
                service.plugins.install(wheel)
            service.refresh_catalog()
            return {'id': payload.operator_id, 'catalog': service.catalog}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
