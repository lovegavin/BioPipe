"""Compile immutable installations once with the interpreter that executes them."""
import importlib.util
import py_compile
import os
from pathlib import Path


def filesystem_path(path):
    value = str(Path(path).resolve())
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        return '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return value


def precompile(directory, *, immutable=True):
    directory = Path(directory)
    mode = (py_compile.PycInvalidationMode.UNCHECKED_HASH if immutable
            else py_compile.PycInvalidationMode.CHECKED_HASH)
    directory = Path(filesystem_path(directory))
    sources = list(directory.rglob('*.py'))
    for source in sources:
        py_compile.compile(str(source), cfile=importlib.util.cache_from_source(str(source)),
                           dfile=source.relative_to(directory).as_posix(), doraise=True,
                           invalidation_mode=mode, optimize=0)
    missing = [str(p) for p in sources if not Path(importlib.util.cache_from_source(str(p))).is_file()]
    if missing:
        raise ValueError(f"Incomplete bytecode coverage: {missing[:5]}")
    return {"sources": len(sources), "compiled": len(sources), "mode": mode.name.lower()}
