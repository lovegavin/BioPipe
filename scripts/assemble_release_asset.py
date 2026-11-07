"""Assemble checksum-verified temporary release parts on the GitHub runner.

Used only for an interrupted local upload. It preserves the already tested
binary bytes and the release's prerelease flag, and removes parts only after a
download of the assembled asset has independently matched the expected hash.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler


class AssetRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and urlsplit(newurl).netloc != urlsplit(req.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def main():
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    repository = os.environ['GH_REPO']
    assert re.fullmatch(r'[\w.-]+/[\w.-]+', repository)
    token = os.environ['GH_TOKEN']
    base = 'https://api.github.com/repos/' + repository
    release_id = int(manifest['release_id'])
    filename = manifest['filename']
    assert re.fullmatch(r'[\w.-]+', filename)

    def api(path, method='GET'):
        request = Request(base + path, method=method,
                          headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json'})
        with urlopen(request, timeout=120) as response:
            data = response.read()
        return json.loads(data) if data else None

    release = api('/releases/' + str(release_id))
    assert release['tag_name'] == manifest['tag']
    assert release['draft'] or release['prerelease'], 'Transfer must not mutate a stable release'
    opener = build_opener(AssetRedirect())

    def download(asset, timeout=120):
        request = Request(base + '/releases/assets/' + str(asset['id']), headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/octet-stream'})
        return opener.open(request, timeout=timeout)
    assets = api(f'/releases/{release_id}/assets?per_page=100')
    assets = {item['name']: item for item in assets}
    output = Path(os.environ.get('RUNNER_TEMP', '.')) / filename
    with output.open('wb') as destination:
        for part in manifest['parts']:
            assert re.fullmatch(r'operon-rc\d+-transfer-\d{3}\.part', part['name'])
            asset = assets[part['name']]
            assert asset['state'] == 'uploaded' and asset['size'] == part['bytes']
            with download(asset) as response:
                data = response.read()
            assert len(data) == part['bytes'] and hashlib.sha256(data).hexdigest() == part['sha256']
            destination.write(data)
    assert output.stat().st_size == manifest['bytes']
    with output.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['sha256']
    def publish(path, expected):
        # Exact-name replacements belong to this transfer, not another release.
        if path.name in assets:
            api('/releases/assets/' + str(assets[path.name]['id']), 'DELETE')
        url = 'https://uploads.github.com/repos/' + repository + f'/releases/{release_id}/assets?name=' + quote(path.name)
        request = Request(url, method='POST', data=path.read_bytes(), headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/octet-stream'})
        with urlopen(request, timeout=600) as response:
            uploaded = json.load(response)
        assert uploaded['state'] == 'uploaded' and uploaded['size'] == path.stat().st_size
        with download(uploaded, timeout=600) as response:
            digest = hashlib.sha256()
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
        assert digest.hexdigest() == expected, 'Published asset checksum differs'
        print(json.dumps({'asset': path.name, 'sha256': expected, 'bytes': path.stat().st_size}))

    publish(output, manifest['sha256'])
    if output.suffix.lower() == '.zip':
        with zipfile.ZipFile(output) as archive:
            names = [name for name in archive.namelist() if name.endswith('/Operon_Setup.exe')]
            assert len(names) == 1
            setup = output.parent / 'Operon_Setup.exe'
            setup.write_bytes(archive.read(names[0]))
            checksum = archive.read(names[0] + '.sha256')
            expected = checksum.decode('ascii').split()[0]
            assert re.fullmatch(r'[a-f0-9]{64}', expected)
            assert hashlib.sha256(setup.read_bytes()).hexdigest() == expected
            publish(setup, expected)
            sidecar = setup.with_suffix('.exe.sha256'); sidecar.write_bytes(checksum)
            publish(sidecar, hashlib.sha256(checksum).hexdigest())
    for part in manifest['parts']:
        api('/releases/assets/' + str(assets[part['name']]['id']), 'DELETE')
    print('Temporary transfer parts removed; draft/prerelease state preserved')


if __name__ == '__main__':
    main()
