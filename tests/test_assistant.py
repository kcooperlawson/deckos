"""DecKoOS Assistant's safety rules: what runs without asking (is_read_only) and what never runs (BLOCKED).
deckos-local and the Assistant's workspace use the same rules, so a command wrongly counted as looking runs unasked there too."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/assistant'))

import assistant  # noqa: E402

LOOKS = [
    'ls -la', 'cat /etc/os-release', 'journalctl -b -p warning', 'journalctl -b | grep error | tail',
    'systemctl status sddm', 'systemctl --user is-active deckos-modes', 'git status', 'git log --oneline',
    'git diff HEAD~1', 'git branch', 'git branch -a', 'git branch --show-current', 'git remote -v',
    'git remote show origin', 'pacman -Qi steam', 'paru -Ss heroic', 'deckos', 'deckos doctor',
    'deckos display status', 'deckos mode status', 'find . -name "*.py"', 'sort -k2 -n data.txt',
    'uniq -c names.txt', 'tree -L 2', 'date +%s', 'rg -n TODO', 'env', 'printenv HOME', 'hostname',
    'hostname -I', 'groups $USER', 'ollama list', 'flatpak list', 'steam --version',
]
ACTS = [
    # runs another program
    'env rm -rf /tmp/x', 'env bash -c id', 'env FOO=1 make', 'rg --pre sh x', 'rg --pre=sh x',
    'find . -exec rm {} +', 'find . -delete', 'git -c core.pager=sh log', 'sudo ls',
    # writes or deletes files
    'find . -fprint /tmp/x', 'find . -fls /tmp/x', 'sort -o /tmp/x a', 'sort -ro /tmp/x a',
    'sort --output=/tmp/x a', 'uniq a /tmp/out', 'tree -o /tmp/x', 'git diff --output=/tmp/x',
    'git log --output=/tmp/x', 'journalctl --vacuum-size=1M', 'journalctl --rotate', 'echo hi > f',
    'cat a | tee b', 'ls; rm x', 'ls && rm x', 'ls || rm x', 'cat $(rm x)',
    # changes repositories or settings
    'git branch -D main', 'git branch new-feature', 'git branch -m old new', 'git remote remove origin',
    'git remote add x y', 'git remote set-url origin z', 'git commit -m x', 'date -s 2020-01-01',
    'hostname newname', 'systemctl restart sddm', 'pacman -S steam', 'pacman -Rns steam',
    'deckos update', 'deckos display set 2', 'deckos mode off', 'flatpak install x', 'ollama rm model',
    'rm file', 'cp a b', 'mv a b', '',
]
BLOCKED = [
    'rm -rf /', 'rm -fr /', 'rm -rf /*', 'sudo rm -rf /', 'rm -rf --no-preserve-root /', 'rm -r -f /home',
    'rm -rf ~', 'rm -rf ~/', 'rm -rf ~/*', 'rm -rf $HOME', 'rm -rf $HOME/*', 'rm -rf "$HOME"',
    'rm -rf ${HOME}/', 'rm -rf /home/tester/', 'mkfs.ext4 /dev/sda1', 'wipefs -a /dev/nvme0n1',
    'sgdisk -Z /dev/sda', 'dd if=/dev/zero of=/dev/sda bs=1M', 'shred -n1 /dev/nvme0n1',
    'cat x > /dev/sda', 'cryptsetup luksFormat /dev/sda2', ':(){ :|:& };:', 'chmod -R 777 /',
]
ALLOWED = [  # dangerous-sounding but scoped; these still need the person's yes
    'rm -rf ~/Downloads/old', 'rm -rf build/', 'rm -rf /tmp/deckos-test', 'rm -rf $HOME/.cache/foo',
    'chmod -R 755 ./site', 'shred secret.txt',
]


class ReadOnly(unittest.TestCase):
    def test_looking_runs_without_asking(self):
        for command in LOOKS:
            with self.subTest(command=command):
                self.assertTrue(assistant.is_read_only(command))

    def test_anything_that_acts_asks_first(self):
        for command in ACTS:
            with self.subTest(command=command):
                self.assertFalse(assistant.is_read_only(command))


class Blocked(unittest.TestCase):
    def test_disasters_are_refused(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertIsNotNone(assistant.blocked_reason(command))

    def test_scoped_commands_are_not_refused(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(assistant.blocked_reason(command))


if __name__ == '__main__':
    unittest.main()
