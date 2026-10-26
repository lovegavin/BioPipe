"""Keep the complete English guide examples executable against the real SDK."""
from pathlib import Path
import re

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def example(name, tmp_path, monkeypatch):
    import importlib.util, sys, json, ast
    source = (ROOT / 'docs' / name).read_text(encoding='utf-8-sig')
    code = re.findall(r'```python\n(.*?)```', source, re.S)[0]
    schema = json.loads(re.findall(r'```json\n(.*?)```', source, re.S)[0])
    tree = ast.parse(code)
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for n in cls.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'parameters_file' for t in n.targets):
                (tmp_path / ast.literal_eval(n.value)).write_text(json.dumps(schema), encoding='utf-8')
    path = tmp_path / (Path(name).stem + '.py')
    path.write_text(code, encoding='utf-8')
    monkeypatch.syspath_prepend(str(tmp_path))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return vars(module)


def test_reader_guide(tmp_path, monkeypatch):
    reader = example('reader_extensions.md', tmp_path, monkeypatch)['NpyReader']()
    path = tmp_path / 'sample.npy'
    np.save(path, np.array([[1., 2.], [3., np.nan]]))
    form = reader.read(path, ['sample', 'feature'], {})
    np.testing.assert_allclose(form.data, [[1, 2], [3, np.nan]])
    assert form.labels['sample'] == {'0': 0, '1': 1}


def test_operator_guide(tmp_path, monkeypatch):
    from biopipe_sdk import Form
    from biopipe_sdk.testing import run_operator
    cls = example('step_extensions.md', tmp_path, monkeypatch)['Scale']
    data = np.array([[1., -9.]])
    form = Form(data=data, dims=['sample', 'feature'],
                labels={'sample': {'s': 0}, 'feature': {'a': 0, 'b': 1}}, info={'missing_code': -9})
    result = run_operator(cls, [form], {'factor': 3})
    np.testing.assert_allclose(result.data, [[3., np.nan]])
    np.testing.assert_allclose(data, [[1., -9.]])
