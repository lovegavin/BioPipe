"""Backed-up conversion of a known old profile before desktop services start."""
import json

from biopipe_sdk.protocol import PROTOCOL_VERSION


def upgrade_profile(profile):
    registry = profile.data_dir / 'plugins/registry.json'
    if not registry.is_file():
        return None
    state = json.loads(registry.read_text(encoding='utf-8-sig'))
    if state.get('package_protocol_version') == PROTOCOL_VERSION:
        return None
    from biopipe.migrate import migrate
    options = ({'profile_dir': profile.profile_dir} if profile.profile_dir else
               {'workspace': profile.workspace, 'data_dir': profile.data_dir})
    # The migration preflight rejects unknown protocols, incompatible external
    # providers and concurrent instances. Publication is backed up and atomic.
    return migrate(**options, apply=True)
