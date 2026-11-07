from pathlib import Path
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings
from src.web.preferences import Preferences, load, save
from operon.user_config import UserConfig
from src.web.storage import atomic_json

ROOT = Path(__file__).resolve().parents[1]


def test_language_is_profile_scoped_and_survives_new_service(tmp_path):
    workspace = tmp_path / 'workspace'
    settings = Settings(workspace, workspace / '.studio', ROOT / 'frontend/dist', testing=True)
    with TestClient(create_app(settings)) as client:
        bootstrap = client.get('/api/bootstrap').json()
        assert bootstrap['preferences'] == {'language': 'system', 'theme': 'system'}
        headers = {'X-Studio-Token': bootstrap['token']}
        assert client.post('/api/preferences', json={'language': 'en'}, headers=headers).status_code == 200
        assert client.post('/api/preferences', json={'theme': 'dark'}, headers=headers).status_code == 200
        assert client.get('/api/preferences').json() == {'language': 'en', 'theme': 'dark'}
        # Old browser caches initialize missing fields only, even on a new port.
        assert client.post('/api/preferences?initialize=true', json={'language': 'zh-CN', 'theme': 'light'}, headers=headers).json() == {'language': 'en', 'theme': 'dark'}
        assert client.post('/api/preferences', json={'language': '../../escape'}, headers=headers).status_code == 422
        assert client.get('/api/preferences').json() == {'language': 'en', 'theme': 'dark'}
        assert client.post('/api/preferences', json={'theme': 'invented'}, headers=headers).status_code == 422
    # A new app/port uses the same profile file, not a browser-origin setting.
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/bootstrap').json()['preferences'] == {'language': 'en', 'theme': 'dark'}
    assert json.loads((workspace / '.studio/config.json').read_text()) == {'language': 'en', 'theme': 'dark'}
    other = tmp_path / 'other'
    with TestClient(create_app(Settings(other, other / '.studio', ROOT / 'frontend/dist', testing=True))) as client:
        assert client.get('/api/bootstrap').json()['preferences'] == {'language': 'system', 'theme': 'system'}


def test_migrates_old_settings_once_without_resurrecting_cleared_choices(tmp_path):
    originals = {'preferences.json': {'language': 'en'},
                 'viewers/settings.json': {'igv': 'example.exe'},
                 'viewers/defaults.json': {'.bed': 'igv'}}
    for path, value in originals.items():
        atomic_json(tmp_path / path, value)
    config = UserConfig(tmp_path)
    assert config.read() == {'language': 'en', 'viewers': {'paths': {'igv': 'example.exe'}, 'defaults': {'.bed': 'igv'}}}
    save(tmp_path, Preferences(theme='dark', language='zh-CN'), initialize=True)
    assert load(tmp_path).model_dump() == {'language': 'en', 'theme': 'dark'}
    config.update(lambda value: value['viewers']['defaults'].clear())
    assert UserConfig(tmp_path).read()['viewers']['defaults'] == {}
    for path, value in originals.items():
        assert json.loads((tmp_path / path).read_text()) == value


def test_concurrent_preference_updates_keep_other_sections(tmp_path):
    UserConfig(tmp_path).update(lambda value: value.update({'future': {'enabled': True}, 'viewers': {'defaults': {'.hic': 'juicebox'}}}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(save, tmp_path, Preferences(language='en')),
                   pool.submit(save, tmp_path, Preferences(theme='dark'))]
        for result in results:
            result.result()
    assert UserConfig(tmp_path).read() == {
        'future': {'enabled': True}, 'viewers': {'defaults': {'.hic': 'juicebox'}}, 'language': 'en', 'theme': 'dark'}
