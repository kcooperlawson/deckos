"""deckos dev-install: never replaces a newer DecKoOS with an older checkout by accident. Runs the real deckos
tool with fake pacman, makepkg and vercmp; nothing is built or installed."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECKOS = ROOT / 'pkg/deckos-settings/rootfs/usr/bin/deckos'


class DevInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'calls'
        self.command('pacman', '[[ $1 == -Q && -n ${INSTALLED:-} ]] && echo "deckos-settings $INSTALLED"\n')
        self.command('makepkg', 'printf "makepkg %s in %s\\n" "$*" "$PWD" >> "$CALLS"\n')
        # vercmp A B: -1, 0 or 1, like pacman's (sort -V is close enough for these versions)
        self.command('vercmp', '[[ $1 == "$2" ]] && { echo 0; exit; }\n'
                     '[[ $(printf "%s\\n%s\\n" "$1" "$2" | sort -V | head -n1) == "$1" ]] && echo -1 || echo 1\n')

    def tearDown(self):
        self.temp.cleanup()

    def command(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + body)
        path.chmod(0o755)

    def checkout(self, name, version):
        path = self.root / name
        (path / 'pkg/deckos-settings').mkdir(parents=True)
        (path / 'VERSION').write_text(version + '\n')
        return path

    def dev_install(self, *args, installed='0.5.5-1', cwd=None):
        env = dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=str(self.root), CALLS=str(self.calls), INSTALLED=installed)
        return subprocess.run(['bash', str(DECKOS), 'dev-install', *args], capture_output=True, text=True,
                              timeout=10, env=env, cwd=cwd or self.root)

    def built(self):
        return self.calls.read_text() if self.calls.exists() else ''

    @unittest.skipIf(os.geteuid() == 0, 'dev-install refuses to run as root')
    def test_an_old_clone_found_by_the_search_is_refused(self):
        self.checkout('deckos', '0.3.15')  # $HOME/deckos: the first place the search looks
        result = self.dev_install()
        self.assertEqual(result.returncode, 1)
        self.assertIn('older than the installed 0.5.5', result.stderr)
        self.assertEqual(self.built(), '')

    @unittest.skipIf(os.geteuid() == 0, 'dev-install refuses to run as root')
    def test_downgrade_only_when_asked(self):
        old = self.checkout('old', '0.3.15')
        result = self.dev_install(str(old), '--downgrade')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'in {old}/pkg/deckos-settings', self.built())

    @unittest.skipIf(os.geteuid() == 0, 'dev-install refuses to run as root')
    def test_same_or_newer_checkout_installs(self):
        for version in ('0.5.5', '0.5.6', '0.10.0'):
            with self.subTest(version=version):
                path = self.checkout('v' + version, version)
                result = self.dev_install(str(path))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'in {path}/pkg/deckos-settings', self.built())

    @unittest.skipIf(os.geteuid() == 0, 'dev-install refuses to run as root')
    def test_first_install_has_nothing_to_compare(self):
        path = self.checkout('fresh', '0.3.15')
        self.assertEqual(self.dev_install(str(path), installed='').returncode, 0)


if __name__ == '__main__':
    unittest.main()
