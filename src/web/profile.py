"""The single directory policy used by Python launchers and the desktop host.

Resolution is read-only. Relative profile overrides are anchored to the user's
home, never cwd or the executable directory. The default remains independent of checkout and executable location.
"""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class StudioProfile:
    profile_dir: Path | None
    workspace: Path
    data_dir: Path

    def as_dict(self):
        return {"profile_dir": str(self.profile_dir) if self.profile_dir else None,
                "workspace": str(self.workspace), "data_dir": str(self.data_dir),
                "registry": str(self.data_dir / "workflows/registry.json")}


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
    workspace_data = data_dir or env.get("BIOPIPE_STUDIO_DATA")
    if workspace is not None:
        if profile_dir is not None:
            raise ValueError("--workspace 与 --profile-dir 不能同时使用。")
        root = expand(workspace, code_root)
        data = expand(workspace_data or ".studio", root)
        if not data.is_relative_to(root):
            raise ValueError("--data-dir 必须位于 --workspace 内。")
        return StudioProfile(None, root, data)
    if workspace_data is not None:
        raise ValueError("BIOPIPE_STUDIO_DATA / --data-dir requires --workspace; use BIOPIPE_STUDIO_HOME / --profile-dir for a shared profile.")
    profile = expand(override or ".biopipe/studio", home)
    return StudioProfile(profile, profile / "workspace", profile / "workspace/.studio")



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
                  workspace=None, data_dir=None):
    from .service import Settings
    profile = resolve_profile(code_root, profile_dir=profile_dir, workspace=workspace, data_dir=data_dir)
    profile.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(profile.data_dir / "matplotlib")
    return Settings(profile.workspace, profile.data_dir, Path(frontend).resolve(),
                    max_upload=upload_limit_from_env(),
                    code_root=Path(code_root).resolve(), desktop=desktop, profile=profile.as_dict(),
                    builtin_routes=True)
