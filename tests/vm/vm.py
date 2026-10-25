"""Drive an installed DeckOS test VM over its serial console, for checks that need a real system
(btrfs, restarts). Not a unit test: run it by hand.

    bash tests/install-test.sh out/deckos-X.iso out/it          # once: an installed test disk
    VM_TMP=out python3 tests/vm/vm.py out/it/disk.img out/it/vars.fd pkg/deckos-settings/rootfs/usr/bin \
        tests/vm/undo_steps.py

Boots DISK with QEMU's snapshot=on (DISK is never written; the guest's writes go to a temp file in
VM_TMP and survive its restarts), serves SCRIPT_DIR at http://10.0.2.2:PORT/ for the guest, logs in
as the install test's user and runs STEPS.py, which gets `vm` and calls vm.run(...) / vm.reboot()."""
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import functools
import http.server

USER, PASSWORD = 'tester', 'deckos-test'  # tests/install-test.sh's answers (a test-only VM)
PROMPT = '@@P@@ '
# systemd's OSC 3008 context markers (ESC ] ... ESC \\) and colour codes
ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[A-Za-z]')


def extra_disks():
    """VM_EXTRA_DISKS=a.img,b.img: more disks for the guest, with the serials a and b
    (/dev/disk/by-id/virtio-a). They are written to: pass copies."""
    args = []
    for path in filter(None, os.environ.get('VM_EXTRA_DISKS', '').split(',')):
        name = os.path.splitext(os.path.basename(path))[0]
        args += ['-drive', f'file={os.path.abspath(path)},format=raw,if=none,id={name}',
                 '-device', f'virtio-blk-pci,drive={name},serial={name}']
    return args


class VM:
    def __init__(self, disk, vars_fd, serve_dir):
        self.work = tempfile.mkdtemp(prefix='deckos-vm-')
        self.disk = os.path.abspath(disk)  # snapshot=on: writes go to a temp file, DISK stays as it is
        self.vars = os.path.join(self.work, 'vars.fd')
        subprocess.run(['cp', vars_fd, self.vars], check=True)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=serve_dir)
        handler.log_message = lambda *a: None
        self.http = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.port = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.sock_path = os.path.join(self.work, 'serial.sock')
        self.log = open(os.path.join(self.work, 'serial.log'), 'w')
        self.buf = ''
        self.ANSI = ANSI  # for steps files
        code = '/usr/share/OVMF/OVMF_CODE_4M.fd'
        self.qemu = subprocess.Popen([
            'qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm', '-cpu', 'host', '-smp', '4', '-m', '4G',
            '-display', 'none', '-monitor', 'none', '-serial', f'unix:{self.sock_path},server=on,wait=on',
            '-drive', f'if=pflash,format=raw,readonly=on,file={code}', '-drive', f'if=pflash,format=raw,file={self.vars}',
            '-drive', f'file={self.disk},format=raw,if=virtio,snapshot=on', '-nic', 'user,model=virtio-net-pci',
            *extra_disks()],
            env=dict(os.environ, TMPDIR=os.environ.get('VM_TMP', '/var/tmp')))
        for _ in range(100):
            if os.path.exists(self.sock_path):
                break
            time.sleep(0.1)
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(self.sock_path)
        self.s.settimeout(0.5)
        print(f'[vm] booting; serial log {self.log.name}', flush=True)

    def read(self):
        try:
            data = self.s.recv(65536).decode(errors='replace')
        except socket.timeout:
            return False
        if not data:
            raise RuntimeError('VM closed its console')
        self.buf += data
        self.log.write(data)
        self.log.flush()
        return True

    def expect(self, pattern, timeout=300):
        deadline = time.time() + timeout
        rx = re.compile(pattern)
        while time.time() < deadline:
            m = rx.search(self.buf)
            if m:
                out, self.buf = self.buf[:m.start()], self.buf[m.end():]
                return out, m
            self.read()
        raise TimeoutError(f'waited {timeout}s for {pattern!r}; last output:\n{self.buf[-1500:]}')

    def send(self, text):
        self.s.sendall(text.encode())

    def login(self):
        self.expect(r'login: ', 900)
        time.sleep(1)
        self.send(USER + '\n')
        self.expect(r'[Pp]assword: ', 60)
        self.send(PASSWORD + '\n')
        time.sleep(2)
        self.send(f"export PS1='{PROMPT}' TERM=dumb; stty -echo cols 250\n")
        self.expect(re.escape(PROMPT), 60)
        self.buf = ''
        print('[vm] logged in', flush=True)

    def run(self, command, timeout=600, ok=True):
        """Run a shell command as the test user; returns (exit code, output)."""
        self.buf = ''
        self.send(f'{command}; echo "@@RC=$?@@"\n')
        out, m = self.expect(r'@@RC=(\d+)@@', timeout)
        self.expect(re.escape(PROMPT), 30)
        code = int(m.group(1))
        out = ANSI.sub('', out).replace('\r', '').strip()
        print(f'$ {command}\n{out}\n[exit {code}]', flush=True)
        if ok and code != 0:
            raise AssertionError(f'{command!r} failed ({code})')
        return code, out

    def sudo(self, command, **kw):
        return self.run(f"echo {PASSWORD} | sudo -S -p '' {command}", **kw)

    def reboot(self):
        self.send(f'echo {PASSWORD} | sudo -S -p "" systemctl reboot\n')
        print('[vm] rebooting', flush=True)
        self.buf = ''
        self.login()

    def close(self):
        try:
            self.send(f'echo {PASSWORD} | sudo -S -p "" systemctl poweroff\n')
            self.qemu.wait(60)
        except Exception:
            self.qemu.kill()
        self.http.shutdown()


if __name__ == '__main__':
    disk, vars_fd, serve_dir, steps = sys.argv[1:5]
    vm = VM(disk, vars_fd, serve_dir)
    try:
        vm.login()
        exec(open(steps).read(), {'vm': vm})
        print('[vm] ALL STEPS PASSED', flush=True)
    finally:
        vm.close()
