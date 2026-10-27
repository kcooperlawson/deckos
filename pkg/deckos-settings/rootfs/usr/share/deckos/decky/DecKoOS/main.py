"""DecKoOS's Decky backend: each call runs /usr/lib/deckos/decky/bridge.py with the system's Python, as the player,
so DecKoOS's own (tested) code does the work and the plugin stays a thin window onto it."""
import asyncio
import json
import os

import decky

BRIDGE = os.environ.get("DECKOS_DECKY_BRIDGE", "/usr/lib/deckos/decky/bridge.py")


def _env():
    """The player's session: pactl finds the sound server through XDG_RUNTIME_DIR."""
    env = dict(os.environ)
    uid = os.getuid()
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{uid}/bus")
    env["HOME"] = decky.DECKY_USER_HOME
    return env


async def _bridge(*args):
    proc = await asyncio.create_subprocess_exec("/usr/bin/python3", BRIDGE, *[str(a) for a in args],
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                env=_env())
    out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
    if proc.returncode != 0:
        decky.logger.warning("bridge %s: %s", args, err.decode(errors="replace").strip())
        return {"ok": False, "error": err.decode(errors="replace").strip() or "DecKoOS didn't answer"}
    return {"ok": True, "out": out.decode(errors="replace")}


class Plugin:
    async def snapshot(self):
        r = await _bridge("snapshot")
        if not r["ok"]:
            return {"error": r["error"]}
        try:
            return json.loads(r["out"])
        except ValueError:
            return {"error": "DecKoOS sent something unreadable"}

    async def power(self, profile):
        return await _bridge("power", profile)

    async def profile(self, game_id, key, value, name=""):
        return await _bridge("profile", game_id, key, value, name)

    async def output(self, name):
        return await _bridge("output", name)

    async def kind(self, kind, percent):
        return await _bridge("kind", kind, int(percent))

    async def eq(self, preset):
        return await _bridge("eq", preset)

    async def _main(self):
        decky.logger.info("DecKoOS panel ready")

    async def _unload(self):
        pass
