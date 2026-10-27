"""Ask the installed generation resolver to prove historical pin availability."""
from .models import Graph


def validated_pins(service, requested):
    if not isinstance(requested, dict):
        raise ValueError('Pin compatibility request must be an object')
    result = {}
    for key, values in requested.items():
        if not isinstance(values, list):
            raise ValueError('Pin compatibility values must be lists')
        for pin in values:
            probe = Graph(nodes=[], edges=[], plugin_lock={key: pin})
            try:
                service.plugins.snapshot(probe)
            except ValueError:
                continue
            result.setdefault(key, []).append(pin)
    return result
