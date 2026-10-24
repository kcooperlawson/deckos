# Snapshot first, end to end on an installed DeckOS (see vm.py): real snapper, real prompts on the serial
# console. A big delete in /home, put back with deckos restore; a sudo delete of system files, put back
# with deckos undo and a restart. Serve pkg/deckos-settings/rootfs (not usr/bin) for this one.
import re

PASSWORD = 'deckos-test'
D = '/usr/local/bin/deckos-new'
SF = '/usr/share/deckos/shell/snapshot-first.bash'


def install():
    vm.run(f'curl -fsS http://10.0.2.2:{vm.port}/usr/bin/deckos -o /tmp/deckos && '
           f'curl -fsS http://10.0.2.2:{vm.port}{SF} -o /tmp/sf.bash && '
           f'echo {PASSWORD} | sudo -S -p "" install -m755 /tmp/deckos {D} && '
           f'echo {PASSWORD} | sudo -S -p "" install -Dm644 /tmp/sf.bash {SF}')


def answered(line, answer):
    """Type LINE, answer the Snapshot first question with ANSWER; returns (exit code, output)."""
    vm.buf = ''
    vm.send(f'{line}; echo "@@RC=$?@@"\n')
    vm.expect(r'\[c\]ancel', 120)
    vm.send(answer)
    out, m = vm.expect(r'@@RC=(\d+)@@', 300)
    after, _ = vm.expect(re.escape('@@P@@ '), 60)
    text = vm.ANSI.sub("", out + after).replace("\r", "")
    print(f'$ {line}  [{answer}]\n{text.strip()}\n[exit {m.group(1)}]', flush=True)
    return int(m.group(1)), text


install()
vm.run('snapper -c home list | tail -3; snapper -c root list | tail -2')
vm.run(f'. {SF}; echo loaded')

# /home: a folder right inside home
vm.run('mkdir -p ~/Pictures/trip && echo photo > ~/Pictures/trip/a.jpg')
code, out = answered('rm -rf ~/Pictures', 'y')
n = re.search(r'deckos restore (\d+)', out).group(1)
code, _ = vm.run('ls ~/Pictures', ok=False); assert code != 0, 'Pictures should be gone'
vm.run(f'{D} restore {n}')
_, text = vm.run('cat ~/Pictures/trip/a.jpg'); assert 'photo' in text, text
# everyday deletes don't ask (would hang waiting for an answer otherwise)
vm.run('mkdir -p ~/proj/.git ~/proj/build && rm -rf ~/proj/build && echo quiet')

# /: system files with sudo, put back by deckos undo after a restart
vm.sudo('sh -c "mkdir -p /opt/deckos-sf && echo cfg > /opt/deckos-sf/settings"')
code, out = answered(f'echo {PASSWORD} | sudo -S -p "" rm -rf /opt/deckos-sf', 'y')
pre = re.search(r'sudo deckos undo (\d+)', out).group(1)
code, _ = vm.run('ls /opt/deckos-sf', ok=False); assert code != 0
vm.sudo(f'{D} undo {pre}')
vm.reboot()
_, text = vm.run('cat /opt/deckos-sf/settings'); assert 'cfg' in text, text
vm.run('cat ~/Pictures/trip/a.jpg')  # /home untouched by the system undo
install()
vm.sudo(f'{D} undo clean')
