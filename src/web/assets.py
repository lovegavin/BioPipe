"""Descriptor-only input planning; file payloads never load optional readers."""
from copy import deepcopy
from pathlib import Path, PureWindowsPath
import re
import os
import uuid

from .graph import GraphError, project_path
from .storage import atomic_json
from .service import read_json
from biopipe.file_formats import reader_extensions, uncompressed_path


def safe_filename(name):
    if (not isinstance(name, str) or not name or len(name) > 180
            or name.startswith('.') or name.endswith((' ', '.'))
            or any(ord(c) < 32 or c in '\\/:*?"<>|' for c in name)
            or PureWindowsPath(name).is_reserved()):
        raise GraphError('文件名无效；请选择没有路径或特殊字符的数据文件。')
    return name


def accepted_extensions(catalog):
    result = set()
    for reader in catalog['readers']:
        result.update(reader_extensions(reader))
        result.update(reader.get('requires_siblings', []))
        for group in (reader.get('file_input') or {}).get('companions', []):
            result.update(''.join(Path(name).suffixes) for name in group)
    return sorted(result)


def plan_input(names, catalog):
    """Choose one data set and validate companions using filenames only."""
    if not isinstance(names, list) or not 1 <= len(names) <= 32:
        raise GraphError('一次请选择一组数据，最多 32 个文件。')
    names = [safe_filename(name) for name in names]
    if len({name.casefold() for name in names}) != len(names):
        raise GraphError('同组文件不能重名（不区分大小写）。')
    present = set(names)
    candidates, incomplete = [], []
    for name in names:
        for reader in catalog['readers']:
            if not any(name.lower().endswith(ext.lower()) for ext in reader_extensions(reader)):
                continue
            path = uncompressed_path(Path(name))
            if any(path.with_suffix(ext).name in present for ext in reader.get('excludes_siblings', [])):
                continue
            required = [path.with_suffix(ext).name for ext in reader.get('requires_siblings', [])]
            groups = (reader.get('file_input') or {}).get('companions', [])
            missing = [s for s in required if s not in present]
            missing += [' / '.join(group) for group in groups if not present.intersection(group)]
            if missing:
                incomplete.append(f"{name}: 缺少配套文件 {', '.join(missing)}")
                continue
            used = {name, *required}
            for group in groups:
                selected = present.intersection(group)
                if len(selected) > 1:
                    raise GraphError(f"{name}: 配套文件存在多个版本，请仅保留一个：{', '.join(sorted(selected))}")
                used.update(selected)
            candidates.append((name, reader, used))
    complete = [item for item in candidates if item[2] == present]
    if len(complete) != 1:
        if incomplete:
            raise GraphError('；'.join(incomplete))
        raise GraphError('无法识别为一组完整数据。请选择一个主文件及其配套文件；格式以 reader 注册表为准。')
    name, reader, _ = complete[0]
    hints = reader.get('file_input') or {}
    dims = deepcopy(hints.get('dims', ['sample', 'feature']))
    return {'filename': name, 'reader': reader['name'], 'source': {
        'dims': dims, 'labels': deepcopy(hints.get('labels', {dim: 'auto' for dim in dims})), 'args': {}}}


class AssetImports:
    def __init__(self, service):
        self.service = service

    def create(self, names):
        plan = plan_input(names, self.service.catalog)
        key = uuid.uuid4().hex
        directory = self.service.assets_dir / key
        directory.mkdir()
        atomic_json(directory / '.upload.json', {'names': names, 'plan': plan, 'complete': False})
        return {'id': key, **plan}

    def load(self, key):
        if not re.fullmatch('[0-9a-f]{32}', key):
            raise GraphError('上传组 ID 无效。')
        directory = self.service.assets_dir / key
        if directory.is_symlink() or directory.resolve().parent != self.service.assets_dir.resolve():
            raise GraphError('上传目录无效。')
        state = read_json(directory / '.upload.json')
        if state is None:
            raise GraphError('找不到上传组，请重新选择文件。')
        return directory, state

    def target(self, key, name):
        safe_filename(name)
        directory, state = self.load(key)
        if state['complete'] or name not in state['names']:
            raise GraphError('文件不属于此上传组，或上传已完成。')
        path = directory / name
        if path.exists() or path.is_symlink():
            raise GraphError('文件已上传，请勿重复上传。')
        return path

    def complete(self, key, base_dir='.'):
        base = project_path(self.service.root, '.', base_dir)
        directory, state = self.load(key)
        if any(not (directory / name).is_file() or (directory / name).is_symlink()
               for name in state['names']):
            raise GraphError('仍有配套文件尚未上传。')
        plan = state['plan']
        path = directory / plan['filename']
        # A binary PLINK BED must not silently become a UCSC interval table.
        if plan['reader'] == 'BedReader' and path.suffix.lower() == '.bed':
            with path.open('rb') as stream:
                if stream.read(2) == b'\x6c\x1b':
                    raise GraphError('这是 PLINK 二进制 BED；请同时选择同名 .bim 和 .fam 文件。')
        state['complete'] = True
        atomic_json(directory / '.upload.json', state)
        source = {**plan['source'], 'path': Path(os.path.relpath(path, base)).as_posix()}
        return {**plan, 'source': source, 'path': source['path'], 'files': state['names']}

    def cancel(self, key):
        directory, state = self.load(key)
        if state['complete']:
            return  # Published data may already be referenced by a canvas.
        if any((directory / ('.' + name + '.part')).exists() for name in state['names']):
            raise GraphError('文件仍在上传，请等待传输结束再取消。')
        for name in state['names']:
            (directory / safe_filename(name)).unlink(missing_ok=True)
            (directory / ('.' + name + '.part')).unlink(missing_ok=True)
        (directory / '.upload.json').unlink()
        directory.rmdir()
