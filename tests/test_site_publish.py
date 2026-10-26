"""DecKoOS Builder's Website card: which release ISOs can go on the site (only ones whose whole run passed, install
tests included), signing only with the DecKoOS key, and the published choice surviving later rebuilds."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/builder'))
sys.path.insert(0, str(ROOT / 'site'))
import site_publish as SP  # noqa: E402


def run(id_, branch='', title='', status='completed', conclusion='success', created='2026-10-26T10:00:00Z'):
    return {'id': id_, 'head_branch': branch, 'event': 'push' if branch else 'workflow_dispatch',
            'display_title': title, 'status': status, 'conclusion': conclusion, 'created_at': created,
            'html_url': f'https://example.org/{id_}', 'run_number': id_}


ISO = [{'name': 'deckos-iso', 'expired': False, 'expires_at': '2026-11-09T02:13:16Z'}]


class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def states(self, versions, tag_runs=(), version_runs=(), arts=None):
        arts = arts or {}
        asked = []

        def artifacts_of(rid):
            asked.append(rid)
            return arts.get(rid, [])
        items = SP.sources(versions, self.out, list(tag_runs), list(version_runs), artifacts_of)
        return {i['version']: i['state'] for i in items}, asked

    def test_versions_from_tags(self):
        self.assertEqual(SP.release_versions(['v0.9.0', 'v0.14.0', 'v0.13.1', 'repo', 'vnext', 'v2026.10.23']),
                         ['0.14.0', '0.13.1', '0.9.0'])

    def test_local_iso_first(self):
        (self.out / 'deckos-0.12.1-x86_64.iso').write_bytes(b'iso')
        self.assertEqual(self.states(['0.12.1'])[0], {'0.12.1': 'local'})

    def test_only_a_passed_run_counts(self):
        tag_runs = [run(1, 'v0.13.1', conclusion='failure'), run(2, 'v0.13.0')]
        states, asked = self.states(['0.13.1', '0.13.0'], tag_runs, arts={1: ISO, 2: ISO})
        self.assertEqual(states, {'0.13.1': 'none', '0.13.0': 'ci'})
        self.assertNotIn(1, asked, 'a failed run is never offered, so its artifacts are not even asked for')

    def test_tag_without_an_iso_or_expired(self):
        tag_runs = [run(3, 'v0.14.0'), run(4, 'v0.12.4')]
        states, _ = self.states(['0.14.0', '0.12.4'], tag_runs,
                                arts={3: [{'name': 'deckos-packages', 'expired': False}],
                                      4: [{'name': 'deckos-iso', 'expired': True}]})
        self.assertEqual(states, {'0.14.0': 'none', '0.12.4': 'none'})

    def test_on_request_builds(self):
        version_runs = [run(5, title='ISO for DecKoOS 0.14.0', status='in_progress', conclusion=None),
                        run(6, title='ISO for DecKoOS 0.13.1', conclusion='failure'),
                        run(7, title='ISO for DecKoOS 0.12.3', conclusion='success')]
        states, _ = self.states(['0.14.0', '0.13.1', '0.12.3'], version_runs=version_runs, arts={7: ISO})
        self.assertEqual(states, {'0.14.0': 'building', '0.13.1': 'failed', '0.12.3': 'ci'})
        # '3.1' is the end of '0.13.1' but not the version: titles match on the whole version
        self.assertEqual(SP.runs_for('3.1', [], version_runs), [])


class SignAndPublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.iso = self.root / 'out/deckos-0.13.0-x86_64.iso'
        self.iso.parent.mkdir()
        self.iso.write_bytes(b'iso')

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_key_no_signature_and_a_stale_one_goes(self):
        sig = self.iso.with_name(self.iso.name + '.sig')
        sig.write_bytes(b'old')
        old = time.time() - 3600
        os.utime(sig, (old, old))
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 2, '', 'no secret key')
        self.assertIn('not signed', SP.sign(self.iso, run=fake))
        self.assertFalse(sig.exists())
        self.assertEqual(len(calls), 1, 'without the key, gpg is never asked to sign')

    def test_signs_with_the_deckos_key_only(self):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, '', '')
        self.assertEqual(SP.sign(self.iso, run=fake), 'signed')
        self.assertIn(SP.FINGERPRINT, calls[1])
        self.assertIn('--local-user', calls[1])

    def test_publish_pins_the_choice(self):
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, 'built 19 pages\n', '')
        self.assertEqual(SP.publish(self.root, self.iso, run=fake), 'built 19 pages')
        self.assertEqual((self.root / 'out/site-iso').read_text().strip(), str(self.iso.resolve()))
        self.assertEqual(calls[0][-2:], ['--iso', str(self.iso)])

    def test_the_site_offers_the_pinned_iso(self):
        import build
        newer = self.root / 'out/deckos-0.14.0-x86_64.iso'
        newer.write_bytes(b'newer')
        pin = self.root / 'out/site-iso'
        old_root, old_pin = build.ROOT, build.PIN
        try:
            build.ROOT, build.PIN = self.root, pin
            site = build.Site.__new__(build.Site)
            self.assertEqual(site.find_iso(None), newer, 'without a pin: the newest release ISO')
            pin.write_text(str(self.iso))
            self.assertEqual(site.find_iso(None), self.iso, 'with one: what Builder published')
            self.iso.unlink()
            self.assertEqual(site.find_iso(None), newer, 'a pin to a deleted ISO falls back')
        finally:
            build.ROOT, build.PIN = old_root, old_pin


if __name__ == '__main__':
    unittest.main()
