"""The single directory policy used by Python launchers and the desktop host.

Resolution is read-only. Relative profile overrides are anchored to the user's
home, never cwd or the executable directory. AppData is a legacy import source,
not a default destination (packaged Windows parents can virtualize AppData).
"""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class StudioProfile:
    profile_dir: Path | None
    workspace: Path
    data_dir: Path
    migrate_legacy: bool = False

    def as_dict(self):
        return {"profile_dir": str(self.profile_dir) if self.profile_dir else None,
                "workspace": str(self.workspace), "data_dir": str(self.data_dir),
                "registry": str(self.data_dir / "workflows/registry.json"),
                "migrate_legacy": self.migrate_legacy}


def resolve_profile(code_root, *, profile_dir=None, workspace=None, data_dir=None,
                    environ=None, home=None):
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    code_root, home = Path(code_root).resolve(), home.resolve()

    def expand(value, base):
        text = os.path.expandvars(str(value))
        if text == "~":
            return home
        if text.startswith(("~/", "~\\")):
            text = str(home / text[2:])
        return (base / text).resolve()

    override = profile_dir or env.get("BIOPIPE_STUDIO_HOME")
    legacy_data = data_dir or env.get("BIOPIPE_STUDIO_DATA")
    if workspace is not None:
        if profile_dir is not None:
            raise ValueError("--workspace 与 --profile-dir 不能同时使用。")
        root = expand(workspace, code_root)
        data = expand(legacy_data or ".studio", root)
        if not data.is_relative_to(root):
            raise ValueError("--data-dir 必须位于 --workspace 内。")
        return StudioProfile(None, root, data)
    if legacy_data is not None:
        raise ValueError("旧 BIOPIPE_STUDIO_DATA / --data-dir 需配合 --workspace；共享目录请改用 BIOPIPE_STUDIO_HOME / --profile-dir。")
    profile = expand(override or ".biopipe/studio", home)
    return StudioProfile(profile, profile / "workspace", profile / "workspace/.studio", not bool(override))


def legacy_locations(code_root, *, environ=None, home=None):
    """Known BioPipe locations only; never scan arbitrary user directories."""
    env = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    root = Path(code_root).resolve()
    candidates = [(root, root / ".local/studio")]
    local = env.get("LOCALAPPDATA")
    if local:
        workspace = Path(local) / "BioPipe Studio/workspace"
        candidates.append((workspace, workspace / ".studio"))
    # Enumerate only the old BioPipe suffix in package-local caches. The package
    # family is discovered, so this also works outside any particular dev tool.
    packages = home / "AppData/Local/Packages"
    if packages.is_dir():
        for data in sorted(packages.glob("*/LocalCache/Local/BioPipe Studio/workspace/.studio")):
            candidates.append((data.parent, data))
    seen = set()
    for workspace, data in candidates:
        key = os.path.normcase(str(data.resolve()))
        if key not in seen and data.is_dir():
            seen.add(key)
            yield workspace.resolve(), data.resolve()


def upload_limit_from_env():
    """Optional explicit limit shared by both launchers; unset/zero is unlimited."""
    raw = os.environ.get("BIOPIPE_STUDIO_MAX_UPLOAD_MB", "0")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("BIOPIPE_STUDIO_MAX_UPLOAD_MB must be a non-negative integer (MiB)") from exc
    if value < 0:
        raise ValueError("BIOPIPE_STUDIO_MAX_UPLOAD_MB must be a non-negative integer (MiB)")
    return value * 1024**2 if value else None


def make_settings(code_root, frontend, *, desktop=False, profile_dir=None,
                  workspace=None, data_dir=None, migrate_legacy=None):
    from .service import Settings
    profile = resolve_profile(code_root, profile_dir=profile_dir, workspace=workspace, data_dir=data_dir)
    profile.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(profile.data_dir / "matplotlib")
    return Settings(profile.workspace, profile.data_dir, Path(frontend).resolve(),
                    max_upload=upload_limit_from_env(),
                    code_root=Path(code_root).resolve(), desktop=desktop, profile=profile.as_dict(),
                    migrate_legacy=profile.migrate_legacy if migrate_legacy is None else migrate_legacy, builtin_routes=True)
