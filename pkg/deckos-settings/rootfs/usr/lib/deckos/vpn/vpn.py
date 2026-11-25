#!/usr/bin/env python3
"""DecKoOS VPN: private browsing through a server of your own (WireGuard). No Qt.

The PC makes its key pair (the private half never leaves it), `setup` prints a script for the server with the PC's
public key in it, and the server answers with `deckos vpn connect HOST:PORT KEY`, which hands NetworkManager a
WireGuard connection: Plasma's network list and Quick Settings show and switch it like any other.
"""
import base64
import ipaddress
import os
import re
import subprocess
import sys
from pathlib import Path

NAME = "DecKoOS VPN"
PORT = 51820
PC_ADDRESS = "10.66.66.2/32"
SERVER_ADDRESS = "10.66.66.1/24"
DNS = "9.9.9.9"  # Quad9: no logs of who asked; the server's own resolver would need setting up first
HOME = Path(os.environ.get("DECKOS_VPN_HOME") or Path.home() / ".config/deckos/vpn")
KEY_RE = re.compile(r"[A-Za-z0-9+/]{42}[AEIMQUYcgkosw480]=")


# X25519 (RFC 7748): Python has no WireGuard key maker and wireguard-tools isn't on every DecKoOS
P = 2**255 - 19


def _x25519(k: bytes, u: bytes) -> bytes:
    k = bytearray(k)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    scalar = int.from_bytes(k, "little")
    x1 = int.from_bytes(u, "little") & ((1 << 255) - 1)
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in reversed(range(255)):
        bit = (scalar >> t) & 1
        swap ^= bit
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = bit
        a, b = (x2 + z2) % P, (x2 - z2) % P
        aa, bb = a * a % P, b * b % P
        e = (aa - bb) % P
        c, d = (x3 + z3) % P, (x3 - z3) % P
        da, cb = d * a % P, c * b % P
        x3, z3 = (da + cb) ** 2 % P, x1 * (da - cb) ** 2 % P
        x2, z2 = aa * bb % P, e * (aa + 121665 * e) % P
    if swap:
        x2, z2 = x3, z3
    return (x2 * pow(z2, P - 2, P) % P).to_bytes(32, "little")


def public_key(private: str) -> str:
    return base64.b64encode(_x25519(base64.b64decode(private), (9).to_bytes(32, "little"))).decode()


def keys():
    """(private, public): made once, private file readable only by you."""
    path = HOME / "private.key"
    if not path.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        HOME.chmod(0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(base64.b64encode(os.urandom(32)).decode() + "\n")
    private = path.read_text().strip()
    return private, public_key(private)


def server_script(pc_public: str) -> str:
    """Runs as root on a fresh Ubuntu/Debian or Oracle Linux/Fedora server; safe to run twice."""
    if not KEY_RE.fullmatch(pc_public):
        raise ValueError("Not a WireGuard key")
    return f"""#!/bin/bash
# DecKoOS VPN server: WireGuard for one DecKoOS PC. Run as root: sudo bash deckos-vpn-server.sh
set -Eeuo pipefail
if command -v apt-get >/dev/null; then
  apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -yq wireguard iptables curl
elif command -v dnf >/dev/null; then
  dnf install -y wireguard-tools iptables curl
else
  echo "Use Ubuntu, Debian, Oracle Linux or Fedora." >&2; exit 1
fi
umask 077
mkdir -p /etc/wireguard
[[ -f /etc/wireguard/server.key ]] || wg genkey > /etc/wireguard/server.key
iface=$(ip -4 route show default | awk '{{print $5; exit}}')
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = {SERVER_ADDRESS}
ListenPort = {PORT}
PrivateKey = $(cat /etc/wireguard/server.key)
# Oracle's images reject everything not allowed above their REJECT rule: these go in first
PostUp = iptables -I INPUT 1 -p udp --dport {PORT} -j ACCEPT; iptables -I FORWARD 1 -i wg0 -j ACCEPT; iptables -I FORWARD 1 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -A POSTROUTING -o $iface -j MASQUERADE
PostDown = iptables -D INPUT -p udp --dport {PORT} -j ACCEPT; iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -D POSTROUTING -o $iface -j MASQUERADE

[Peer]
PublicKey = {pc_public}
AllowedIPs = {PC_ADDRESS}
EOF
echo net.ipv4.ip_forward=1 > /etc/sysctl.d/90-deckos-vpn.conf
sysctl -q -p /etc/sysctl.d/90-deckos-vpn.conf
systemctl enable -q wg-quick@wg0
systemctl restart wg-quick@wg0
ip=$(curl -4 -fsS https://api.ipify.org || echo SERVER-ADDRESS)
echo
echo "Done. On your DecKoOS PC run:"
echo "  deckos vpn connect $ip:{PORT} $(wg pubkey < /etc/wireguard/server.key)"
echo
echo "On Oracle Cloud also open UDP port {PORT}: your instance's subnet > Security list > Add ingress rule"
echo "(source 0.0.0.0/0, UDP, destination port {PORT})."
"""


def endpoint(text: str) -> str:
    """HOST:PORT, HOST alone (port 51820), or [IPv6]:PORT."""
    m = re.fullmatch(r"\[([0-9A-Fa-f:]+)\](?::(\d+))?|([A-Za-z0-9.-]+)(?::(\d+))?", text.strip())
    if not m:
        raise ValueError(f"Not a server address: {text!r}")
    host, port = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    if m.group(1):
        ipaddress.IPv6Address(host)
        host = f"[{host}]"
    port = int(port or PORT)
    if not 0 < port < 65536:
        raise ValueError("The port must be 1-65535")
    return f"{host}:{port}"


def client_config(private: str, server_key: str, server: str) -> str:
    if not KEY_RE.fullmatch(server_key):
        raise ValueError("That isn't a WireGuard key: copy the whole line the server printed")
    # ::/0 too: with no IPv6 address inside, IPv6 goes nowhere instead of around the VPN
    return (f"[Interface]\nPrivateKey = {private}\nAddress = {PC_ADDRESS}\nDNS = {DNS}\n\n"
            f"[Peer]\nPublicKey = {server_key}\nEndpoint = {endpoint(server)}\nAllowedIPs = 0.0.0.0/0, ::/0\n"
            "PersistentKeepalive = 25\n")


def run(*cmd, check=True):
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def present():
    """The NetworkManager connection's state: None (not set up), 'on' or 'off'."""
    out = run("nmcli", "-t", "-f", "NAME,TYPE,ACTIVE", "connection", "show", check=False).stdout
    for line in out.splitlines():
        name, kind, active = (line.rsplit(":", 2) + ["", ""])[:3]
        if name.replace("\\:", ":") == NAME and kind == "wireguard":
            return "on" if active == "yes" else "off"
    return None


def connect(server: str, server_key: str):
    private, _ = keys()
    conf = client_config(private, server_key.strip(), server)
    if present():
        run("nmcli", "connection", "delete", NAME)
    # nmcli names the connection after the file; it's read once and removed
    path = HOME / "deckos-vpn.conf"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(conf)
    try:
        out = run("nmcli", "connection", "import", "type", "wireguard", "file", str(path)).stdout
    finally:
        path.unlink(missing_ok=True)
    uuid = re.search(r"\(([0-9a-f-]{36})\)", out)
    ref = ["uuid", uuid.group(1)] if uuid else ["id", "deckos-vpn"]
    run("nmcli", "connection", "modify", *ref, "connection.id", NAME, "connection.autoconnect", "no")
    run("nmcli", "connection", "up", "id", NAME)


def switch(on: bool):
    if not present():
        raise RuntimeError("No DecKoOS VPN yet: run deckos vpn setup")
    run("nmcli", "connection", "up" if on else "down", "id", NAME)


def status() -> str:
    state = present()
    if state is None:
        return "Not set up. Run deckos vpn setup."
    if state == "off":
        return "Set up, off. deckos vpn on"
    peer = run("nmcli", "-g", "wireguard.peers", "connection", "show", NAME, check=False).stdout.strip()
    return "On: your traffic goes through your server." + (f"\n{peer}" if peer else "")


USAGE = """deckos vpn setup                      make this PC's key, print the server script
deckos vpn connect HOST[:PORT] KEY    add the VPN (the line the server printed)
deckos vpn on|off|status|remove"""


def main(argv):
    cmd = argv[0] if argv else "status"
    try:
        if cmd == "setup":
            _, pub = keys()
            script = Path.home() / "deckos-vpn-server.sh"
            script.write_text(server_script(pub))
            print(f"Saved {script}\n\nCopy it to your server and run it there as root:\n"
                  f"  scp {script} USER@SERVER:\n  ssh USER@SERVER sudo bash deckos-vpn-server.sh\n\n"
                  "It ends with a deckos vpn connect line: run that here.")
        elif cmd == "connect" and len(argv) == 3:
            connect(argv[1], argv[2])
            print("Connected. Switch it in Quick Settings' network list, or deckos vpn on|off.")
        elif cmd in ("on", "off"):
            switch(cmd == "on")
            print(status())
        elif cmd == "status":
            print(status())
        elif cmd == "remove":
            if present():
                run("nmcli", "connection", "delete", NAME)
            print("Removed. Your key stays in ~/.config/deckos/vpn so the server still knows this PC.")
        elif cmd == "public-key":
            print(keys()[1])
        else:
            print(USAGE)
            return 2
    except (ValueError, RuntimeError) as error:
        print(error)  # stdout: the Hub shows it
        return 1
    except subprocess.CalledProcessError as error:
        print((error.stderr or error.stdout or str(error)).strip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
