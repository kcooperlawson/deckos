"""Snapshot first: which commands ask, and the real prompt in an interactive bash (a pseudo-terminal),
with a fake snapper and a throwaway home folder. Nothing is deleted outside the temp folder."""
import os
import pty
import re
import select
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'pkg/deckos-settings/rootfs/usr/share/deckos/shell/snapshot-first.bash'


class Kind(unittest.TestCase):
    """__deckos_sf_kind LINE, run on its own (the file returns early outside interactive shells)."""

    @classmethod
    def setUpClass(cls):
        text = SCRIPT.read_text()
        cls.func = re.search(r'^__deckos_sf_kind\(\) \{.*?^\}\n', text, re.S | re.M).group(0)
        cls.temp = tempfile.TemporaryDirectory()
        cls.home = Path(cls.temp.name) / 'me'
        (cls.home / 'Documents').mkdir(parents=True)
        (cls.home / 'code/app/.git').mkdir(parents=True)
        (cls.home / 'code/app/build').mkdir()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def kind(self, line, cwd=None):
        out = subprocess.run(['bash', '-c', self.func + '__deckos_sf_kind "$1"', '_', line], capture_output=True,
                             text=True, env=dict(PATH='/usr/bin:/bin', HOME=str(self.home)),
                             cwd=cwd or self.home, timeout=10)
        return out.stdout.strip()

    def test_big_deletes_in_home_ask(self):
        for line in ('rm -rf ~/Documents', 'rm -r Documents/', 'rm -rf "$HOME"', 'rm -fr ~/Documents ~/x',
                     'rm --recursive ~/.config', 'cd /tmp && rm -rf ~/Documents', 'rm -rf ~/code/app',
                     'FOO=1 rm -Rf ~/Documents', 'sudo rm -rf /home/someone', 'sudo rm -rf /home/someone/Music'):
            with self.subTest(line=line):
                self.assertEqual(self.kind(line), 'home')

    def test_system_deletes_with_sudo_ask_for_a_system_snapshot(self):
        for line in ('sudo rm -rf /etc/sddm.conf.d', 'sudo -E rm -r /usr/lib/foo', 'sudo /usr/bin/rm -rf /opt/app',
                     'sudo -u root rm -rf /etc/x', 'echo pw | sudo -S -p "" rm -rf /opt/app'):
            with self.subTest(line=line):
                self.assertEqual(self.kind(line), 'root')

    def test_everyday_commands_do_not_ask(self):
        for line in ('rm -rf build/', 'rm -rf ~/code/app/build', 'rm file.txt', 'rm -f ~/Documents/a.txt',
                     'ls -r ~', 'sudo rm /etc/foo.bak', 'sudo rm -rf /tmp/x', 'rm -rf /tmp/deckos-test',
                     'sudo pacman -Rns steam', 'git rm -r src', 'sudo rm -rf /home/someone/a/b', 'echo rm -rf ~', 'sudo rm -rf /run/media/me/USB/old'):
            with self.subTest(line=line):
                self.assertEqual(self.kind(line, cwd=self.home / 'code/app'), '')


class Interactive(unittest.TestCase):
    """The prompt itself: bash -i in a pseudo-terminal, typing like a person."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.home = root / 'home'
        (self.home / 'Documents').mkdir(parents=True)
        (self.home / 'Documents/keep.txt').write_text('x')
        self.bin = root / 'bin'
        self.bin.mkdir()
        self.calls = root / 'calls'
        # fake snapper: logs its arguments, prints snapshot numbers 7 (pre) then 8
        (self.bin / 'snapper').write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALLS"\n'
                                          '[[ " $* " == *" --print-number "* ]] && echo 7\nexit 0\n')
        (self.bin / 'snapper').chmod(0o755)
        self.configs = root / 'configs'
        self.configs.mkdir()
        (self.configs / 'home').write_text('')
        text = SCRIPT.read_text().replace('/etc/snapper/configs/', f'{self.configs}/')
        self.script = root / 'snapshot-first.bash'
        self.script.write_text(text)
        rc = root / 'rc'
        rc.write_text(f'PS1="PROMPT> "\nHISTFILE=/dev/null\n. {self.script}\n')
        env = dict(PATH=f'{self.bin}:/usr/bin:/bin', HOME=str(self.home), CALLS=str(self.calls), TERM='dumb')
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(self.home)
            # --norc: Arch's bash reads /etc/bash.bashrc even with --rcfile, and that sources the
            # installed Snapshot first, not this checkout's. So no rc files; the test's comes first.
            os.execve('/bin/bash', ['bash', '--noprofile', '--norc', '-i'], env)
        self.out = ''
        self.type(f'. {rc}\n')
        self.expect('PROMPT> ')

    def tearDown(self):
        try:
            os.write(self.fd, b'exit\n')
            os.waitpid(self.pid, 0)
        except OSError:
            pass
        os.close(self.fd)
        self.temp.cleanup()

    def expect(self, text, timeout=10):
        deadline = time.time() + timeout
        while text not in self.out:
            if time.time() > deadline:
                raise AssertionError(f'never saw {text!r} in:\n{self.out}')
            if select.select([self.fd], [], [], 0.2)[0]:
                self.out += os.read(self.fd, 4096).decode(errors='replace')
        before, _, self.out = self.out.partition(text)
        return before

    def type(self, text):
        os.write(self.fd, text.encode())

    def calls_made(self):
        return self.calls.read_text() if self.calls.exists() else ''

    def test_yes_takes_a_pre_and_post_snapshot_around_the_command(self):
        self.type('rm -rf ~/Documents\n')
        self.expect('[c]ancel')
        self.type('y')
        self.expect('Undo it: deckos restore 7')
        self.expect('PROMPT> ')
        self.assertFalse((self.home / 'Documents').exists())
        calls = self.calls_made().splitlines()
        self.assertEqual(len(calls), 2, calls)
        self.assertIn('-c home create --type pre', calls[0])
        self.assertIn('rm -rf ~/Documents', calls[0])
        self.assertIn('--type post --pre-number 7', calls[1])

    def test_cancel_runs_nothing(self):
        self.type('rm -rf ~/Documents; touch ran\n')
        self.expect('[c]ancel')
        self.type('c')
        self.expect('Cancelled.')
        self.expect('PROMPT> ')
        self.type('echo next\n')  # the shell is still usable
        self.expect('next')
        self.assertTrue((self.home / 'Documents/keep.txt').exists())
        self.assertFalse((self.home / 'ran').exists())
        self.assertEqual(self.calls_made(), '')

    def test_no_runs_it_without_a_snapshot(self):
        self.type('rm -rf ~/Documents\n')
        self.expect('[c]ancel')
        self.type('n')
        self.expect('PROMPT> ')
        self.assertFalse((self.home / 'Documents').exists())
        self.assertEqual(self.calls_made(), '')

    def test_everyday_commands_never_ask(self):
        (self.home / 'build').mkdir()
        (self.home / 'proj/.git').mkdir(parents=True)
        (self.home / 'proj/build').mkdir()
        self.type('rm -rf proj/build; echo done-$((1+1))\n')
        before = self.expect('done-2')
        self.assertNotIn('snapshot', before)
        self.assertFalse((self.home / 'proj/build').exists())

    def test_deckos_terminal_gets_a_marker_for_its_undo_bar(self):
        self.type('rm -rf ~/Documents\n')
        self.expect('[c]ancel')
        self.type('y')
        self.assertNotIn('\x1b]7766;', self.expect('PROMPT> '))  # not in other terminals
        (self.home / 'Documents').mkdir()
        self.type('export TERM_PROGRAM=deckos-terminal; rm -rf ~/Documents\n')
        self.expect('[c]ancel')
        self.type('y')
        self.assertIn('\x1b]7766;deckos-snapshot=home:7\x07', self.expect('PROMPT> '))

    def test_turned_off_in_shell_conf(self):
        conf = self.home / '.config/deckos'
        conf.mkdir(parents=True)
        (conf / 'shell.conf').write_text('SNAPSHOT_FIRST=0\n')
        self.type('rm -rf ~/Documents; echo gone\n')
        before = self.expect('gone')
        self.assertNotIn('[c]ancel', before)


if __name__ == '__main__':
    unittest.main()
