"""Machine-local interpreter hint shared by Python startup and the Windows host.

This bootstrap file is independent of canvas profiles: the host needs an
interpreter before it can ask Python to resolve the full Studio profile.
It is a hint, never a substitute for probing version and dependencies.
"""
import importlib.util
import json
import logging
import os
from pathlib import Path
import sys
import tempfile


# NumPy backs Form, the memory store and bounded matrix previews. Scientific
# Readers/analyses beyond that core are prepared in managed execution targets.
CORE_MODULES = ("numpy", "yaml", "psutil",
                "fastapi", "uvicorn", "jsonschema", "pydantic", "packaging", "httpx", "paramiko")


def runtime_config_path(*, environ=None, home=None):
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    value = env.get("OPERON_RUNTIME_CONFIG") or ".operon/runtime.json"
    # The override is home-relative, like Studio's profile overrides, never cwd-relative.
    return (home / value).resolve()


def remember_runtime(*, path=None):
    """Remember only a usable current interpreter, using an atomic replacement.

    A read-only user home must not prevent a working Studio from starting.
    Diagnostics/CLI imports do not call this function; successful UI startup does.
    Setup-owned runtimes never publish a machine-wide hint: their bundled
    interpreter can disappear on uninstall and must not redirect portable copies.
    """
    from .installation import isolated_root, profile_id
    installation = isolated_root(Path(__file__).resolve().parents[1])
    if installation is not None:
        profile_id(installation)  # Invalid identities must still fail closed.
        return False
    if sys.version_info < (3, 11) or any(importlib.util.find_spec(name) is None for name in CORE_MODULES):
        return False
    destination = Path(path) if path is not None else runtime_config_path()
    temporary = None
    try:
        payload = {"schema_version": 1, "python": str(Path(sys.executable).absolute())}
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".runtime-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(payload, output, indent=2)
            output.write("\n")
        os.replace(temporary, destination)
        return True
    except OSError:
        logging.warning("Unable to remember the Operon Python runtime at %s", destination, exc_info=True)
        return False
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
