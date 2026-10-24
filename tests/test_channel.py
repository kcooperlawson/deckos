"""deckos channel: switching between stable and testing updates. Runs the real deckos tool on a copy
of deckos-repo, with a fake curl; never touches /etc or the network."""
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECKOS = ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos'
SHIPPED = ROOT / 'pkg/deckos-settings/rootfs/etc/pacman.d/deckos-repo'


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.conf = self.root / 'deckos-repo'
        self.conf.write_text(SHIPPED.read_text())
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # The fake curl answers like GitHub: MOCK_MISSING=1 is a channel that hasn't been published yet.
        curl = self.bin / 'curl'
        curl.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALLS"\n[[ ${MOCK_MISSING:-0} == 0 ]]\n')
        curl.chmod(0o755)
        text = DECKOS.read_text()
        # Both must be found: otherwise the copy would aim at the real /etc file.
        self.assertEqual(text.count('REPO_CONF=/etc/pacman.d/deckos-repo\n'), 1)
        self.assertEqual(text.count('  need_root channel "$want"\n'), 1)
        text = text.replace('REPO_CONF=/etc/pacman.d/deckos-repo\n', f'REPO_CONF={self.conf}\n')
        text = text.replace('  need_root channel "$want"\n', '')  # the tests run as a normal user
        self.tool = self.root / 'deckos'
        self.tool.write_text(text)
        self.calls = self.root / 'calls'

    def tearDown(self):
        self.temp.cleanup()

    def deckos(self, *args, **env):
        return subprocess.run(['bash', str(self.tool), 'channel', *args], capture_output=True, text=True, timeout=10,
                              env=dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=str(self.root), CALLS=str(self.calls), **env))

    def server(self):
        return [line for line in self.conf.read_text().splitlines() if line.startswith('Server')]

    def test_new_installs_are_on_stable(self):
        self.assertEqual(self.deckos().stdout, 'channel=stable\n')

    def test_switching_changes_only_the_release_in_the_server_line(self):
        before = self.conf.read_text()
        result = self.deckos('testing')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.server(), ['Server = https://github.com/kcooperlawson/deckos/releases/download/repo-testing'])
        self.assertEqual(self.deckos().stdout, 'channel=testing\n')
        self.assertIn('/releases/download/repo-testing/deckos.db', self.calls.read_text())
        self.assertEqual(self.deckos('stable').returncode, 0)
        self.assertEqual(self.conf.read_text(), before)  # comments and SigLevel untouched

    def test_a_channel_that_is_not_published_changes_nothing(self):
        before = self.conf.read_text()
        result = self.deckos('testing', MOCK_MISSING='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("isn't reachable", result.stderr)
        self.assertEqual(self.conf.read_text(), before)

    def test_a_fork_keeps_its_own_owner_and_repo(self):
        self.conf.write_text('SigLevel = Required\nServer = https://github.com/someone/deckos-fork/releases/download/repo\n')
        self.assertEqual(self.deckos('testing').returncode, 0)
        self.assertEqual(self.server(), ['Server = https://github.com/someone/deckos-fork/releases/download/repo-testing'])

    def test_a_hand_edited_server_is_left_alone(self):
        self.conf.write_text('Server = file:///mnt/usb/deckos\n')
        result = self.deckos('testing')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.conf.read_text(), 'Server = file:///mnt/usb/deckos\n')
        self.assertEqual(self.deckos().stdout, 'channel=none\n')

    def test_unknown_channel_is_a_usage_error(self):
        self.assertEqual(self.deckos('beta').returncode, 2)


if __name__ == '__main__':
    unittest.main()
