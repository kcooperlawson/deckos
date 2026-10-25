"""deckos ask: talk to DecKoOS Assistant in the terminal.

    deckos ask "install OBS and set it up for streaming"
    deckos ask                      (a conversation; an empty line or Ctrl+D ends it)
    deckos ask --model gemma4:12b ...
"""
import itertools
import sys
import threading

from assistant import Session, Tools, pick_model

TTY = sys.stdout.isatty()
ACC, SUB, WARN, BOLD, OFF = (("\033[38;2;76;141;255m", "\033[38;2;140;148;166m", "\033[38;2;245;184;75m",
                              "\033[1m", "\033[0m") if TTY else ("",) * 5)


class Spinner:
    """"Thinking…" while the model works, so a 10-second answer doesn't look stuck."""

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        if TTY:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self):
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if self._stop.wait(0.1):
                break
            sys.stdout.write(f"\r{SUB}{frame} thinking…{OFF}")
            sys.stdout.flush()
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join()


spinner = None


def pause_spinner():
    global spinner
    if spinner:
        spinner.__exit__()
        spinner = None


def confirm(title, detail):
    pause_spinner()
    print(f"\n{WARN}{BOLD}? {title}{OFF}")
    for line in detail.splitlines():
        print(f"  {line}")
    try:
        answer = input(f"{WARN}Do it? [y/N] {OFF}").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


def say(text):
    pause_spinner()
    print(f"{ACC}›{OFF} {text}")


def echo(line):
    print(f"  {SUB}{line}{OFF}")


def ask(session, text):
    global spinner
    spinner = Spinner().__enter__()
    try:
        answer = session.ask(text)
    finally:
        pause_spinner()
    print(f"\n{answer}\n")


def main():
    args = sys.argv[1:]
    model = None
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    model = pick_model(model)
    if not model:
        print("No local model is downloaded yet. Run: deckos ai setup", file=sys.stderr)
        return 1
    session = Session(model, Tools(confirm, say, echo))
    print(f"{SUB}DecKoOS Assistant · {model} · on this PC{OFF}")
    text = " ".join(args).strip()
    try:
        if text:
            ask(session, text)
            return 0
        while True:
            try:
                text = input(f"{ACC}{BOLD}› {OFF}").strip()
            except EOFError:
                print()
                return 0
            if not text:
                return 0
            ask(session, text)
    except KeyboardInterrupt:
        pause_spinner()
        print()
        return 130
    except OSError as e:
        pause_spinner()
        print(f"Couldn't reach Ollama ({e}). Is it running? systemctl status ollama", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
