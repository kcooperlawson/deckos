"""Session lifecycle tests with fake commands; never touches the running display manager."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos'


class GamingSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'calls'
        self.profile = self.root / 'steam-profile'
        self.profile.write_text('CLIENTCMD="steam -gamepadui"\n')
        self.env = dict(PATH=f'{self.bin}:/usr/bin', HOME=str(self.root),
                        XDG_STATE_HOME=str(self.root / 'state'), DESKTOP_SESSION='deckos-gaming',
                        CALLS=str(self.calls))
        for command in ('steam', 'gamescope', 'steamos-session-select', 'sudo', 'systemctl', 'journalctl'):
            self.command(command, f'printf "%s\\n" "{command} $*" >> "$CALLS"\n')
        # like an idle machine: no session switch is pending (MOCK_ACTIVE=1 pretends one is)
        self.command('systemctl', 'printf "%s\\n" "systemctl $*" >> "$CALLS"\n'
                     '[[ $1 != is-active ]] || exit $(( ${MOCK_ACTIVE:-0} ? 0 : 3 ))\n')
        self.command('gamescope-session-plus', 'exit "${MOCK_STATUS:-0}"\n')
        self.movie = self.root / 'deckos-startup.webm'
        self.movie.write_bytes(b'webm')
        text = (SCRIPTS / 'gaming-session').read_text().replace(
            '/usr/share/gamescope-session-plus/sessions.d/steam', str(self.profile)).replace(
            '/usr/share/deckos/branding/deckos-startup.webm', str(self.movie))
        self.launcher = self.root / 'gaming-session'
        self.launcher.write_text(text)

    def tearDown(self):
        self.temp.cleanup()

    def command(self, name, contents):
        path = self.bin / name
        path.write_text('#!/bin/bash\n' + contents)
        path.chmod(0o755)
        return path

    def run_script(self, script=None, *args):
        return subprocess.run(['bash', str(script or self.launcher), *args], env=self.env,
                              capture_output=True, text=True, timeout=5)

    def test_missing_profile_blocks_preflight_without_stopping_desktop(self):
        self.profile.unlink()
        result = self.run_script(None, '--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Steam session profile', result.stderr)
        self.assertFalse(self.calls.exists())

    def test_preflight_has_no_session_side_effects(self):
        self.assertEqual(self.run_script(None, '--check').returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_nested_start_is_refused(self):
        self.env['DESKTOP_SESSION'] = 'plasma'
        self.env['XDG_CURRENT_DESKTOP'] = 'KDE'
        self.assertEqual(self.run_script().returncode, 2)
        self.assertFalse(self.calls.exists())

    def test_normal_and_failed_exits_cleanup_session(self):
        for status in (0, 7):
            with self.subTest(status=status):
                self.env['MOCK_STATUS'] = str(status)
                result = self.run_script()
                self.assertEqual(result.returncode, status)
                calls = self.calls.read_text()
                self.assertIn('systemctl --user stop gamescope-session-plus@steam.service', calls)
                self.assertIn('systemctl --user stop graphical-session.target', calls)
                self.assertIn('XDG_DESKTOP_PORTAL_DIR', calls)
                self.assertIn(f'status {status}', (self.root/'state/deckos/gaming-session.log').read_text())

    def test_startup_movie_is_linked_but_a_users_own_movie_stays(self):
        target = self.root / '.local/share/Steam/config/uioverrides/movies/deck_startup.webm'
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(target.resolve(), self.movie)
        target.unlink()
        target.write_bytes(b'mine')
        self.assertEqual(self.run_script().returncode, 0)
        self.assertFalse(target.is_symlink())
        self.assertEqual(target.read_bytes(), b'mine')

    def test_service_reads_overrides_and_translates_disabled_vrr(self):
        source = (SCRIPTS / 'gaming-service').read_text()
        base = self.root/'system.conf'
        base.write_text('SCREEN_WIDTH=3840\nADAPTIVE_SYNC=1\n')
        userdir = self.root/'.config/deckos'
        userdir.mkdir(parents=True)
        (userdir/'gaming.conf').write_text('SCREEN_WIDTH=1920\nADAPTIVE_SYNC=0\n')
        output = self.root/'environment'
        upstream = self.command('upstream', 'printf "%s %s %s\\n" "$SCREEN_WIDTH" "${ADAPTIVE_SYNC-unset}" "$OUTPUT_CONNECTOR" > "'+str(output)+'"\n')
        detect = self.command('deckos', 'echo DP-1\n')
        source = source.replace('/usr/lib/environment.d/60-deckos-gaming.conf', str(self.root/'absent'))
        source = source.replace('/etc/deckos/gaming.conf', str(base))
        source = source.replace('/usr/bin/deckos', str(detect))
        source = source.replace('/usr/share/gamescope-session-plus/gamescope-session-plus', str(upstream))
        service = self.root/'service'
        service.write_text(source)
        result = self.run_script(service)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text().strip(), '1920 unset DP-1')
        (userdir/'gaming.conf').write_text('SCREEN_WIDTH=2560\nADAPTIVE_SYNC=1\nOUTPUT_CONNECTOR=HDMI-A-1\n')
        self.assertEqual(self.run_script(service).returncode, 0)
        self.assertEqual(output.read_text().strip(), '2560 1 HDMI-A-1')

    def test_stop_post_queues_target_stop_without_deadlock(self):
        result = self.run_script(SCRIPTS/'gaming-cleanup')
        self.assertEqual(result.returncode, 0)
        self.assertIn('systemctl --user --no-block stop graphical-session.target', self.calls.read_text())

    def switch_script(self):
        self.env['SUDO_USER'] = 'testuser'
        self.command('id', 'echo wheel\n')
        self.launcher.chmod(0o755)
        sessions = self.root/'sessions'
        sessions.mkdir()
        (sessions/'deckos-gaming.desktop').touch()
        source = (SCRIPTS/'session-switch').read_text()
        source = source.replace('/etc/sddm.conf.d', str(self.root/'sddm'))
        source = source.replace('/usr/lib/deckos/gaming-session', str(self.launcher))
        source = source.replace('/usr/share/wayland-sessions', str(sessions))
        script = self.root/'switch'
        script.write_text(source)
        return script

    def test_incomplete_install_cannot_schedule_a_logout(self):
        script = self.switch_script()
        self.profile.unlink()
        self.command('systemd-run', 'echo scheduled >> "$CALLS"\n')
        result = self.run_script(script, 'gaming')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root/'sddm/zz-deckos-session.conf').exists())

    def test_scheduling_failure_removes_autologin(self):
        script = self.switch_script()
        self.command('systemd-run', 'exit 1\n')
        result = self.run_script(script, 'gaming')
        self.assertEqual(result.returncode, 1)
        self.assertIn('autologin was cleared', result.stderr)
        self.assertFalse((self.root/'sddm/zz-deckos-session.conf').exists())

    def test_pending_switch_is_not_scheduled_twice(self):
        # a second click while the first switch waits would restart SDDM again and kill the new session
        script = self.switch_script()
        self.command('systemd-run', 'echo scheduled >> "$SCHEDULED"\n')
        scheduled = self.root / 'scheduled'
        env = dict(self.env, MOCK_ACTIVE='1', SCHEDULED=str(scheduled))
        result = subprocess.run(['bash', str(script), 'gaming'], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Already switching', result.stderr)
        self.assertFalse(scheduled.exists())


if __name__ == '__main__':
    unittest.main()
