"""Private Windows Python: use long-path imports only when ordinary lookup fails.

Normal module identities and __file__ paths remain unchanged. ZIP/custom path
hooks still handle non-directories. Package resources use native paths because
their filenames can be longer than the importable package itself. No scientific
imports or host policy edits.
"""
import importlib.machinery as machinery
import os
import sys


def _native_path(path):
    absolute = os.path.abspath(path)
    if absolute.startswith('\\\\?\\'):
        return absolute
    return '\\\\?\\UNC\\' + absolute[2:] if absolute.startswith('\\\\') else '\\\\?\\' + absolute


class _PackageResources:
    def get_resource_reader(self, fullname):
        if not self.is_package(fullname):
            return None
        from importlib.resources.readers import FileReader
        from types import SimpleNamespace
        return FileReader(SimpleNamespace(path=_native_path(self.path)))


class _SourceLoader(_PackageResources, machinery.SourceFileLoader):
    pass


class _BytecodeLoader(_PackageResources, machinery.SourcelessFileLoader):
    pass


class _ExtensionLoader(_PackageResources, machinery.ExtensionFileLoader):
    pass


class FallbackFinder:
    def __init__(self, ordinary, native):
        self.ordinary, self.native = ordinary, native

    def find_spec(self, fullname, target=None):
        spec = self.ordinary.find_spec(fullname, target) if self.ordinary else None
        if spec is not None and spec.loader is not None:
            # File discovery may honor Windows long-path policy while the DLL
            # loader still rejects the same unprefixed path (notably Python 3.11).
            if (isinstance(spec.loader, machinery.ExtensionFileLoader)
                    and spec.origin and len(os.path.abspath(spec.origin)) >= 260):
                return self.native.find_spec(fullname, target) or spec
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
        (_ExtensionLoader, machinery.EXTENSION_SUFFIXES),
        (_SourceLoader, machinery.SOURCE_SUFFIXES),
        (_BytecodeLoader, machinery.BYTECODE_SUFFIXES))

    def _windows_imports(path):
        absolute = os.path.abspath(path)
        if absolute.startswith('\\\\?\\'):
            return _hook(path)
        extended = _native_path(absolute)
        native = _hook(extended)  # ImportError lets ZIP and custom hooks continue.
        try:
            ordinary = _hook(path)
        except ImportError:
            ordinary = None
        return FallbackFinder(ordinary, native)

    sys.path_hooks.insert(0, _windows_imports)
    sys.path_importer_cache.clear()
