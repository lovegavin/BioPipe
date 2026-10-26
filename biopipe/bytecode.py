"""Compile immutable installations once with the interpreter that executes them."""
import compileall
import importlib.util
import py_compile
from pathlib import Path


def precompile(directory, *, immutable=True):
    directory = Path(directory)
    mode = (py_compile.PycInvalidationMode.UNCHECKED_HASH if immutable
            else py_compile.PycInvalidationMode.CHECKED_HASH)
    if not compileall.compile_dir(str(directory), quiet=1, force=True,
                                 invalidation_mode=mode, optimize=0):
        raise ValueError(f"Python compilation failed: {directory}")
    sources = list(directory.rglob('*.py'))
    missing = [str(p) for p in sources if not Path(importlib.util.cache_from_source(str(p))).is_file()]
    if missing:
        raise ValueError(f"Incomplete bytecode coverage: {missing[:5]}")
    return {"sources": len(sources), "compiled": len(sources), "mode": mode.name.lower()}
