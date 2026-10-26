"""Small mapping whose iteration lists identities without importing providers."""
from collections.abc import MutableMapping


class LazyRegistry(MutableMapping):
    def __init__(self):
        self.factories, self.loaded = {}, {}

    def register(self, key, factory):
        self.loaded.pop(key, None)
        self.factories[key] = factory

    def __getitem__(self, key):
        if key not in self.loaded:
            self.loaded[key] = self.factories[key]()
        return self.loaded[key]

    def __setitem__(self, key, value):
        self.factories.pop(key, None)
        self.loaded[key] = value

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.loaded.pop(key, None)
        self.factories.pop(key, None)

    def __iter__(self):
        return iter(dict.fromkeys([*self.factories, *self.loaded]))

    def __len__(self):
        return len(set(self.factories) | set(self.loaded))

    def __contains__(self, key):
        return key in self.factories or key in self.loaded

    def clear(self):
        self.factories.clear()
        self.loaded.clear()


def reader_proxy(descriptor, factory):
    """Route with descriptor metadata; import a Reader only for payload access."""
    from src.reader.base import Reader
    class DeferredReader(Reader):
        _instance = None

        def implementation(self):
            if self._instance is None:
                self._instance = factory()()
            return self._instance

        def read(self, *args, **kwargs):
            return self.implementation().read(*args, **kwargs)

        def probe(self, *args, **kwargs):
            return self.implementation().probe(*args, **kwargs)

        def read_to_disk(self, *args, **kwargs):
            return self.implementation().read_to_disk(*args, **kwargs)
    DeferredReader.__name__ = descriptor['entry_point'].split(':')[1]
    for key in ('extensions', 'requires_siblings', 'excludes_siblings', 'handles_compression', 'file_input', 'parameters_schema'):
        if key in descriptor:
            setattr(DeferredReader, key, descriptor[key])
    DeferredReader.output_contract = descriptor['contracts']['output']
    DeferredReader.supports_disk_read = 'disk' in descriptor['resources']['memory_modes']
    DeferredReader.disk_protocol = descriptor['resources'].get('disk_protocol')
    DeferredReader._declaration = descriptor
    return DeferredReader()
