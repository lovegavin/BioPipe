"""Descriptor-only Reader dispatch shared by canvas, workers and imports."""
from pathlib import Path

from .file_formats import COMPRESSION_SUFFIXES, compression_extensions, primary_ext, uncompressed_path


def candidates(readers, path, reader_id=None, *, check_siblings=False):
    """An explicit stable ID overrides suffix inference, never compression rules.

    Excluded siblings disambiguate automatic routing only. Required companions
    still apply to an explicit reader. No implementation code is imported.
    """
    if reader_id is not None:
        if not isinstance(reader_id, str) or not reader_id:
            raise ValueError('Reader selector must be a non-empty registered ID')
        readers = [item for item in readers if item['id'] == reader_id]
        if len(readers) != 1:
            raise ValueError(f'Unknown or ambiguous Reader ID: {reader_id}')
    if not path:
        return list(readers) if reader_id else []
    path = Path(path)
    primary = uncompressed_path(path)
    result = []
    for reader in readers:
        if not reader_id and primary_ext(path) not in reader['extensions']:
            continue
        if path.suffix.lower() in COMPRESSION_SUFFIXES and path.suffix.lower() not in compression_extensions(reader):
            continue
        if check_siblings:
            if any(not primary.with_suffix(suffix).exists() for suffix in reader.get('requires_siblings', [])):
                continue
            if not reader_id and any(primary.with_suffix(suffix).exists() for suffix in reader.get('excludes_siblings', [])):
                continue
        result.append(reader)
    return result
