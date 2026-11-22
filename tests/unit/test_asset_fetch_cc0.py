"""Offline tests for the pinned CC0 fetcher. A fake opener replaces the network."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.assets import fetch_cc0
from tools.assets.provenance import ROOT, Refusal

PAYLOAD = b'PK\x03\x04 synthetic archive bytes ' * 40
URL = 'https://dl.polyhaven.org/file/ph-assets/Textures/zip/1k/rock_01/rock_01_1k.zip'


def pin(payload=PAYLOAD, **changes):
    row = {'id': 'rock_01', 'source': 'polyhaven', 'url': URL,
           'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
           'licence_id': 'CC0-1.0'}
    row.update(changes)
    return row


def manifest(*rows):
    return json.dumps({'schema': 'cc0-pins.v1', 'pins': list(rows)}).encode()


class FakeResponse(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


def opener_for(data, *, final=None, calls=None):
    def open_url(url, timeout):
        if calls is not None:
            calls.append(url)
        return FakeResponse(data, final or url)
    return open_url


class ManifestTests(unittest.TestCase):
    def refused(self, *rows, **extra):
        with self.assertRaises(Refusal):
            fetch_cc0.load_pins(manifest(*rows))

    def test_valid_manifest(self):
        self.assertEqual(fetch_cc0.load_pins(manifest(pin()))[0]['id'], 'rock_01')
        ambient = pin(id='bricks', source='ambientcg', url='https://ambientcg.com/get?file=Bricks001_1K-JPG.zip',
                      sha256='a' * 64)
        self.assertEqual(len(fetch_cc0.load_pins(manifest(pin(), ambient))), 2)

    def test_preview_thumbnails_and_non_archives_refused(self):
        self.refused(pin(url='https://cdn.polyhaven.com/asset_img/primary/rock_01.png?height=780'))
        self.refused(pin(url='https://dl.polyhaven.org/asset_img/primary/rock_01.zip'))
        self.refused(pin(url='https://dl.polyhaven.org/file/rock_01.png'))
        self.refused(pin(url='https://dl.polyhaven.org/file/rock_01.zip?x=1'))

    def test_url_shape_refused(self):
        for url in ('http://dl.polyhaven.org/a.zip', 'https://evil.example/a.zip',
                    'https://user@dl.polyhaven.org/a.zip', 'https://dl.polyhaven.org:8443/a.zip',
                    'https://dl.polyhaven.org/a.zip#frag', 'https://dl.polyhaven.org/../a.zip',
                    'https://dl.polyhaven.org/a b.zip', 'ftp://dl.polyhaven.org/a.zip', ''):
            self.refused(pin(url=url))
        for url in ('https://ambientcg.com/get?file=../a.zip', 'https://ambientcg.com/get?file=a.png',
                    'https://ambientcg.com/get?file=a.zip&x=1', 'https://ambientcg.com/other?file=a.zip'):
            self.refused(pin(source='ambientcg', url=url))

    def test_pin_fields_licence_and_limits_refused(self):
        self.refused(pin(licence_id='CC-BY-4.0'))
        self.refused(pin(sha256='A' * 64))
        self.refused(pin(sha256='abc'))
        self.refused(pin(bytes=0))
        self.refused(pin(bytes=True))
        self.refused(pin(bytes=fetch_cc0.MAX_ARCHIVE_BYTES + 1))
        self.refused(pin(id='../escape'))
        self.refused(pin(source='sketchfab'))
        self.refused({**pin(), 'extra': 1})
        self.refused(pin(), pin(sha256='b' * 64))
        self.refused(pin(), pin(id='other'))
        for data in (b'[]', b'{}', b'{"schema":"cc0-pins.v1","pins":[]}', b'not json',
                     b'{"schema":"cc0-pins.v1","pins":[],"pins":[]}'):
            with self.assertRaises(Refusal):
                fetch_cc0.load_pins(data)

    def test_total_bytes_limit(self):
        size = fetch_cc0.MAX_ARCHIVE_BYTES
        rows = [pin(id='p%d' % i, sha256=('%064x' % (i + 1)), bytes=size)
                for i in range(fetch_cc0.MAX_TOTAL_BYTES // size + 1)]
        self.refused(*rows)


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'cache'
        self.pins = fetch_cc0.load_pins(manifest(pin()))

    def test_cache_inside_repository_symlink_or_relative_refused(self):
        with self.assertRaises(Refusal):
            fetch_cc0.prepare_cache(ROOT / 'build' / 'cc0-cache')
        with self.assertRaises(Refusal):
            fetch_cc0.prepare_cache(Path('relative'))
        link = Path(self.temp.name) / 'link'
        os.symlink(self.temp.name, link)
        with self.assertRaises(Refusal):
            fetch_cc0.prepare_cache(link / 'cache')
        (Path(self.temp.name) / '.git').mkdir()
        with self.assertRaises(Refusal):
            fetch_cc0.prepare_cache(self.cache)

    def test_verify_only_never_touches_network(self):
        def forbidden(*args):
            raise AssertionError('network used')
        with patch.object(fetch_cc0, 'urllib_opener', forbidden):
            result = fetch_cc0.fetch(self.pins, self.cache)
        self.assertEqual(result['rock_01']['state'], 'missing')

    def test_download_verifies_and_content_addresses(self):
        calls = []
        result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True,
                                 opener=opener_for(PAYLOAD, calls=calls))
        entry = result['rock_01']
        self.assertEqual(entry['state'], 'downloaded')
        self.assertEqual(entry['file'], 'cc0/' + self.pins[0]['sha256'] + '.zip')
        self.assertEqual((self.cache / entry['file']).read_bytes(), PAYLOAD)
        self.assertEqual(calls, [URL])
        # Second run hits the cache and does not open the network.
        again = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True,
                                opener=opener_for(b'', calls=calls))
        self.assertEqual(again['rock_01']['state'], 'ok')
        self.assertEqual(calls, [URL])
        self.assertEqual(fetch_cc0.fetch(self.pins, self.cache)['rock_01']['state'], 'ok')
        self.assertEqual([p.name for p in (self.cache / 'cc0').iterdir()],
                         [self.pins[0]['sha256'] + '.zip'])

    def test_failures_leave_no_files(self):
        cases = {'fetch.sha256_mismatch': PAYLOAD[:-1] + b'X',
                 'fetch.size_mismatch': PAYLOAD[:-5],
                 'fetch.byte_limit': PAYLOAD + b'extra'}
        for reason, data in cases.items():
            result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True, opener=opener_for(data))
            self.assertEqual(result['rock_01'], {'state': 'failed', 'file': result['rock_01']['file'],
                                                 'reason': reason})
            self.assertEqual(list((self.cache / 'cc0').iterdir()), [], reason)

    def test_redirect_to_preview_or_foreign_host_refused(self):
        cases = {'https://dl.polyhaven.org/asset_img/primary/rock.zip': 'fetch.url_not_archive',
                 'https://evil.example/a.zip': 'fetch.url_not_archive',
                 'http://dl.polyhaven.org/a.zip': 'fetch.url_invalid'}
        for final, reason in cases.items():
            result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True,
                                     opener=opener_for(PAYLOAD, final=final))
            self.assertEqual(result['rock_01']['state'], 'failed')
            self.assertEqual(result['rock_01']['reason'], reason)
            self.assertEqual(list((self.cache / 'cc0').iterdir()), [])

    def test_network_error_and_time_limit(self):
        def broken(url, timeout):
            raise OSError('boom')
        result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True, opener=broken)
        self.assertEqual(result['rock_01']['reason'], 'fetch.network_or_io')
        result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True,
                                 opener=opener_for(PAYLOAD), max_seconds=-1)
        self.assertEqual(result['rock_01']['reason'], 'fetch.time_limit')
        self.assertEqual(list((self.cache / 'cc0').iterdir()), [])

    def test_corrupt_cache_entry_is_replaced(self):
        directory = fetch_cc0.prepare_cache(self.cache)
        (directory / (self.pins[0]['sha256'] + '.zip')).write_bytes(b'corrupt')
        self.assertFalse(fetch_cc0.verify_cached(self.pins[0], directory))
        result = fetch_cc0.fetch(self.pins, self.cache, download_enabled=True, opener=opener_for(PAYLOAD))
        self.assertEqual(result['rock_01']['state'], 'downloaded')
        self.assertTrue(fetch_cc0.verify_cached(self.pins[0], directory))

    def test_symlinked_cache_entry_not_trusted(self):
        directory = fetch_cc0.prepare_cache(self.cache)
        outside = Path(self.temp.name) / 'outside.zip'
        outside.write_bytes(PAYLOAD)
        os.symlink(outside, directory / (self.pins[0]['sha256'] + '.zip'))
        self.assertFalse(fetch_cc0.verify_cached(self.pins[0], directory))


class CliTests(unittest.TestCase):
    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = fetch_cc0.main(list(argv))
        return code, json.loads(out.getvalue())

    def test_default_is_offline_and_output_has_no_absolute_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'pins.json'
            path.write_bytes(manifest(pin()))
            code, report = self.run_main('--manifest', str(path), '--cache', str(Path(temp) / 'cache'))
            self.assertEqual(code, 1)
            self.assertEqual(report['pins']['rock_01']['state'], 'missing')
            self.assertNotIn(temp, json.dumps(report))
            path.write_bytes(b'{}')
            code, report = self.run_main('--manifest', str(path), '--cache', str(Path(temp) / 'cache'))
            self.assertEqual((code, report['valid']), (1, False))
            self.assertNotIn(temp, json.dumps(report))


if __name__ == '__main__':
    unittest.main()
