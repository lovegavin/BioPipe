# src/task/step/steps/__init__.py
"""Step modules.

Each module here defines one or more Step subclasses with a
non-default ``name``. The router in ``src/task/step/__init__.py``
scans this package.

Adding a new step: drop a new module with a Step subclass in this
directory. No registry to edit.
"""