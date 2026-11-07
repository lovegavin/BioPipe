"""Private Windows Python: use long-path imports only when ordinary lookup fails.

Normal module identities and __file__ paths remain unchanged. ZIP/custom path
hooks still handle non-directories. No scientific imports or host policy edits.
"""
import importlib.machinery as machinery
import os
import sys


class FallbackFinder:
    def __init__(self, ordinary, native):
        self.ordinary, self.native = ordinary, native

    def find_spec(self, fullname, target=None):
        spec = self.ordinary.find_spec(fullname, target) if self.ordinary else None
        if spec is not None and spec.loader is not None:
            return spec
        # A long __init__.py can look like a namespace package to the ordinary
        # finder. Prefer its actual implementation when the native alias sees it.
        return self.native.find_spec(fullname, target) or spec

    def invalidate_caches(self):
        if self.ordinary:
            self.ordinary.invalidate_caches()
        self.native.invalidate_caches()


if os.name == 'nt':
    _hook = machinery.FileFinder.path_hook(
        (machinery.ExtensionFileLoader, machinery.EXTENSION_SUFFIXES),
        (machinery.SourceFileLoader, machinery.SOURCE_SUFFIXES),
        (machinery.SourcelessFileLoader, machinery.BYTECODE_SUFFIXES))

    def _windows_imports(path):
        absolute = os.path.abspath(path)
        if absolute.startswith('\\\\?\\'):
            return _hook(path)
        extended = '\\\\?\\UNC\\' + absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\' + absolute
        native = _hook(extended)  # ImportError lets ZIP and custom hooks continue.
        try:
            ordinary = _hook(path)
        except ImportError:
            ordinary = None
        return FallbackFinder(ordinary, native)

    sys.path_hooks.insert(0, _windows_imports)
    sys.path_importer_cache.clear()
