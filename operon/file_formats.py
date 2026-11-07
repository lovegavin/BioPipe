"""Metadata-only external compression rules shared by import and execution."""
from pathlib import Path

WRAPPERS = ('.gz', '.bz2', '.xz')
# Recognize zstd for a useful rejection unless a native Reader explicitly opts in.
COMPRESSION_SUFFIXES = (*WRAPPERS, '.zst')


def compression_extensions(reader):
    hints = reader.get('file_input') or {}
    default = [] if reader.get('handles_compression') else WRAPPERS
    return [suffix.lower() for suffix in hints.get('compression', default)]


def uncompressed_path(path):
    path = Path(path)
    return path.with_suffix('') if path.suffix.lower() in COMPRESSION_SUFFIXES else path


def reader_extensions(reader):
    return [ext + suffix for ext in reader['extensions']
            for suffix in ['', *compression_extensions(reader)]]


def primary_ext(path):
    return uncompressed_path(Path(path)).suffix.lower()
