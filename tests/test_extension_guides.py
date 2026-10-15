"""Keep the complete English guide examples executable against the real SDK."""
from pathlib import Path
import re

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def example(name):
    source = (ROOT / 'docs' / name).read_text(encoding='utf-8')
    namespace = {}
    exec(re.findall(r'```python\n(.*?)```', source, re.S)[0], namespace)
    return namespace


def test_reader_guide(tmp_path):
    reader = example('reader_extensions.md')['NpyReader']()
    path = tmp_path / 'sample.npy'
    np.save(path, np.array([[1., 2.], [3., np.nan]]))
    form = reader.read(path, ['sample', 'feature'], {})
    np.testing.assert_allclose(form.data, [[1, 2], [3, np.nan]])
    assert form.labels['sample'] == {'0': 0, '1': 1}


def test_operator_guide():
    from biopipe_sdk import Form
    from biopipe_sdk.testing import run_operator
    cls = example('step_extensions.md')['Scale']
    data = np.array([[1., -9.]])
    form = Form(data=data, dims=['sample', 'feature'],
                labels={'sample': {'s': 0}, 'feature': {'a': 0, 'b': 1}}, info={'missing_code': -9})
    result = run_operator(cls, [form], {'factor': 3})
    np.testing.assert_allclose(result.data, [[3., np.nan]])
    np.testing.assert_allclose(data, [[1., -9.]])
