"""deckos-local: the local model as an MCP server, so Claude Code can hand it bulky reading.

A 5,000-line build log, a journal, a big config: Claude Code passes the path (or a read-only command)
and a question, the local model reads it on this PC's graphics card, and only the short answer goes
back into Claude's context. Registered with `deckos ai claude-link` (claude mcp add --scope user).

MCP over stdio: JSON-RPC 2.0, one message per line. No SDK, so nothing to install.
"""
import json
import os
import sys
import time
from pathlib import Path

from assistant import chat, is_read_only, pick_model, plain, run, summarize

VERSION = (Path("/usr/share/deckos/version").read_text().strip() if Path("/usr/share/deckos/version").exists() else "dev")
# About 25 parts of 40,000 characters: a minute or two on a 16 GB card. More is cut from the start, since
# errors are usually at the end; Claude is told so it can narrow the command or file instead.
MAX_TEXT = 1_000_000

INSTRUCTIONS = """deckos-local runs a local model (on this PC's GPU, free, private) that reads text so you don't \
have to. Use local_digest when answering needs a lot of text but only a little of it matters: long logs, \
build or test output, journalctl, big files, many files at once. Ask a specific question; you get a short \
answer with the exact lines that matter. It reads up to 1 MB per call (about a minute): narrow logs \
first (journalctl -p warning -b, -u UNIT, --since). It's weaker than you at reasoning and code: don't use it for \
design, edits or anything you'd need to double-check anyway. If it says a game is running, read the text \
yourself."""

TOOLS = [
    {"name": "local_digest",
     "description": "Read files, a read-only command's output, or text locally and answer a question about it. "
                    "For long logs, build output, journals and big files: returns a short answer quoting the lines "
                    "that matter instead of the whole text.",
     "inputSchema": {"type": "object", "properties": {
         "question": {"type": "string", "description": "what to find out, as specific as possible"},
         "paths": {"type": "array", "items": {"type": "string"}, "description": "files to read"},
         "command": {"type": "string", "description": "a read-only command whose output to read "
                                                      "(journalctl, pacman -Q, systemctl status, git log, ...)"},
         "text": {"type": "string", "description": "text to read, if it's not in a file"}},
         "required": ["question"]}},
    {"name": "local_ask",
     "description": "Ask the local model something simple and self-contained (draft a short message, explain an "
                    "error string, convert a format). Free, but much weaker than you.",
     "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}},
    {"name": "local_status",
     "description": "Which local model deckos-local uses, whether it's loaded, and whether a game has it paused.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def gaming():
    """The game running, if any: workload modes unloaded the model for it, and loading 13 GB back would hurt it."""
    state = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "deckos-mode"
    try:
        values = dict(l.split("=", 1) for l in state.read_text().splitlines() if "=" in l)
    except OSError:
        return None
    return values.get("game") or "a game" if values.get("mode") == "gaming" else None


def read_path(path):
    p = Path(path).expanduser()
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > MAX_TEXT:
            f.seek(size - MAX_TEXT)
        data = f.read().decode(errors="replace")
    head = f"===== {p} ({size // 1024} KB" + (", only the last 1 MB" if size > MAX_TEXT else "") + ") =====\n"
    return head + data


def local_digest(question, paths=None, command=None, text=None):
    parts = []
    for path in paths or []:
        try:
            parts.append(read_path(path))
        except OSError as e:
            parts.append(f"===== {path}: couldn't read it ({e.strerror or e}) =====")
    if command:
        if not is_read_only(command):
            raise ValueError("deckos-local only runs read-only commands; run this one yourself")
        code, out = run(plain(command), timeout=120, limit=MAX_TEXT)
        parts.append(f"===== $ {command} (exit {code}) =====\n{out}")
    if text:
        parts.append(text)
    if not parts:
        raise ValueError("give paths, a command or text to read")
    body = "\n\n".join(parts)
    cut = len(body) > MAX_TEXT
    if cut:
        body = body[-MAX_TEXT:]
    t = time.monotonic()
    model = pick_model()
    answer = summarize(body, question, model)
    note = " — only the last 1 MB: narrow it (journalctl -p warning, -u UNIT, --since) to read the rest" if cut or "…" == body[:1] else ""
    return f"{answer}\n\n(deckos-local read {len(body) // 1024} KB with {model} in {time.monotonic() - t:.0f} s{note})"


def call_tool(name, args):
    game = gaming()
    if game and name != "local_status":
        raise RuntimeError(f"{game} is running: the local model is paused for it. Read the text yourself.")
    if name == "local_digest":
        return local_digest(**args)
    if name == "local_ask":
        model = pick_model()
        return chat(model, [{"role": "user", "content": args["prompt"]}]).get("content", "").strip()
    if name == "local_status":
        from assistant import api
        loaded = [m["name"] for m in api("/api/ps", timeout=5).get("models", [])]
        return json.dumps({"model": pick_model(), "loaded": loaded, "paused_for_game": game})
    raise ValueError(f"no tool called {name}")


def reply(id_, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": id_}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method, id_, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if id_ is None:  # a notification (initialized, cancelled): nothing to answer
            continue
        if method == "initialize":
            reply(id_, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "deckos-local", "version": VERSION},
                        "instructions": INSTRUCTIONS})
        elif method == "ping":
            reply(id_, {})
        elif method == "tools/list":
            reply(id_, {"tools": TOOLS})
        elif method == "tools/call":
            try:
                text = call_tool(params.get("name"), params.get("arguments") or {})
                reply(id_, {"content": [{"type": "text", "text": text}]})
            except Exception as e:  # the error goes back to Claude as the tool's answer
                reply(id_, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        else:
            reply(id_, error={"code": -32601, "message": f"unknown method {method}"})


if __name__ == "__main__":
    main()
