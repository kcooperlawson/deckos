"""deckos updates: why a check failed, and the keyring refresh that keeps it from failing. Runs the real deckos tool
with fake checkupdates and gpg on PATH and a temp cache; never touches the network or pacman's keyring."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'pkg/deckos-settings'
DECKOS = PKG / 'rootfs/usr/bin/deckos'
UNITS = PKG / 'rootfs/usr/lib/systemd/system'


class UpdatesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, name, body):
        f = self.bin / name
        f.write_text('#!/bin/bash\n' + body + '\n')
        f.chmod(0o755)

    def updates(self, *args, checkupdates=1, stale=False):
        # checkupdates: 0 updates found, 2 nothing to update, 1 couldn't fetch. gpg says "checking the trustdb"
        # (and fails, as a user can't write root's keyring) when the trust database is due a refresh.
        self.fake('checkupdates', f'[[ {checkupdates} == 0 ]] && echo "linux 6.1-1 -> 6.2-1"; exit {checkupdates}')
        self.fake('gpg', 'echo "gpg: checking the trustdb" >&2; exit 2' if stale else 'exit 0')
        return subprocess.run(['bash', str(DECKOS), 'updates', *args], capture_output=True, text=True, timeout=20,
                              env=dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=str(self.root),
                                       XDG_CACHE_HOME=str(self.root / 'cache'), PACMAN_GNUPG=str(self.root / 'gnupg')))

    def values(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(line.split('=', 1) for line in result.stdout.splitlines())

    def test_a_stale_keyring_is_named_not_blamed_on_the_network(self):
        v = self.values(self.updates(stale=True))
        self.assertIn('keyring needs a refresh', v['error'])
        self.assertIn('sudo pacman-key --updatedb', v['error'])
        self.assertLess(len(v['error']), 80, 'Quick Settings shows it on one line')

    def test_otherwise_it_is_the_connection(self):
        self.assertEqual(self.values(self.updates())['error'], 'No connection to the package mirrors')

    def test_why_for_the_hub(self):
        self.assertIn('keyring', self.updates('--why', stale=True).stdout)
        self.assertEqual(self.updates('--why').stdout, 'No connection to the package mirrors\n')

    def test_a_working_check_has_no_error(self):
        v = self.values(self.updates(checkupdates=0, stale=True))
        self.assertEqual((v['repo'], v.get('error')), ('1', None), 'gpg is only asked after a failure')

    def test_the_keyring_is_refreshed_daily_and_after_install(self):
        service = (UNITS / 'deckos-keyring.service').read_text()
        self.assertIn('ExecStart=/usr/bin/pacman-key --updatedb', service)
        timer = (UNITS / 'deckos-keyring.timer').read_text()
        for line in ('OnCalendar=daily', 'OnBootSec=', 'Persistent=true', 'WantedBy=timers.target'):
            self.assertIn(line, timer)
        install = (PKG / 'deckos-settings.install').read_text()
        self.assertIn('pacman-key --updatedb', install)
        self.assertIn('systemctl enable deckos-keyring.timer', install)


if __name__ == '__main__':
    unittest.main()
