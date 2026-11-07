"""Cancelled installation must not publish a partially compiled dependency."""
import json
import importlib.util
import marshal
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from operon.plugins import process_context
from operon.targets import TargetBuilder


@pytest.mark.parametrize('immutable, flags, mode', [(True, 1, 'unchecked_hash'), (False, 3, 'checked_hash')])
def test_compiler_worker_preserves_hash_mode_and_relative_filenames(tmp_path, immutable, flags, mode):
    from operon.bytecode import precompile
    source = tmp_path/'Unicode 空间'/'fixture.py'
    source.parent.mkdir()
    source.write_text('raise RuntimeError("Compilation must not execute the source")\n', encoding='utf-8')
    result = precompile(source.parent, immutable=immutable)
    assert result == {'sources': 1, 'compiled': 1, 'mode': mode}
    cache = Path(importlib.util.cache_from_source(str(source))).read_bytes()
    assert int.from_bytes(cache[4:8], 'little') == flags
    assert marshal.loads(cache[16:]).co_filename == 'fixture.py'


def test_cancel_during_install_prevents_compilation_and_target_receipt(tmp_path, monkeypatch):
    cancel = threading.Event()
    manager = SimpleNamespace(directory=tmp_path)
    builder = TargetBuilder(manager, {})
    destination = None

    def pip(paths, module, args, directory, **kwargs):
        nonlocal destination
        assert module == 'pip'
        if '--dry-run' in args:
            report = Path(args[args.index('--report')+1])
            report.write_text(json.dumps({'install': [{
                'metadata': {'name': 'synthetic-fixture', 'version': '1.0'},
                'download_info': {'url': 'file:///synthetic-fixture.whl'}
            }]}), encoding='utf-8')
        else:
            destination = Path(args[args.index('--target')+1])
            (destination/'fixture.py').write_text('VALUE = 42\n', encoding='utf-8')
            cancel.set()

    monkeypatch.setattr('operon.targets.invoke', pip)
    previous = getattr(process_context, 'cancel', None)
    process_context.cancel = cancel
    try:
        with pytest.raises(ValueError, match='cancelled'):
            builder.prepare(['synthetic-fixture==1.0'])
    finally:
        process_context.cancel = previous
    assert destination is not None
    assert not (destination/'operon-target.json').exists()
    assert not list(destination.rglob('*.pyc'))
    assert not builder.shared and not builder.prepared
