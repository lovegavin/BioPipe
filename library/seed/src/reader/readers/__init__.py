# src/reader/readers/__init__.py
"""Reader modules.

Each module here defines one Reader subclass. The router in
``src/reader/__init__.py`` scans this package and registers each
subclass by its declared extensions.

Adding a new reader: drop a new module with a Reader subclass in this
directory. No registry to edit.
"""