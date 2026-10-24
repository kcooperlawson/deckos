"""DeckOS Bench: repeatable system and game benchmarks, with offline reports."""
import argparse
import subprocess
import sys
from pathlib import Path

from bench_core import RUNS, load, run_suite, save
from report import compare_report, run_report
from bench_experiment import SETTINGS, run_experiment
from runners import ALL, GAMES, SYSTEM


def positive(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("use a positive integer")
    if number < 1:
        raise argparse.ArgumentTypeError("use a positive integer")
    return number


def show(path, open_report=True):
    print(f"\nReport: {path}")
    if open_report:
        try:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            print("Open this file in a browser to view the report.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("app", help="open the native DeckOS Bench application")
    commands.add_parser("list", help="show available benchmarks and saved runs")
    for command in ("system", "games", "run"):
        sub = commands.add_parser(command)
        if command == "run":
            sub.add_argument("keys", help="comma-separated runner keys; see list")
        sub.add_argument("--repeat", type=positive, default=3)
        sub.add_argument("--label", default="")
        sub.add_argument("--no-open", action="store_true", help="save the report without opening a browser")
    sub = commands.add_parser("experiment", help="the same tests with one setting changed, A and B in turn")
    sub.add_argument("setting", choices=list(SETTINGS), help="power (profile) or ai-loaded (model in graphics memory)")
    sub.add_argument("a", help="value A, e.g. performance / unloaded")
    sub.add_argument("b", help="value B, e.g. balanced / loaded")
    sub.add_argument("--tests", default="cpu-7z,memory", help="comma-separated runner keys (default: cpu-7z,memory)")
    sub.add_argument("--repeat", type=positive, default=3, help="turns per value (3+ for a verdict)")
    sub.add_argument("--label", default="")
    sub.add_argument("--no-open", action="store_true")
    sub = commands.add_parser("compare", help="compare saved runs by name, path, last or last-1")
    sub.add_argument("a")
    sub.add_argument("b")
    sub.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "app":
        from pathlib import Path
        return subprocess.call([sys.executable, str(Path(__file__).with_name("bench_app.py"))])
    if args.command in (None, "list"):
        print("Runners:")
        for key, cls in ALL.items():
            ok, why = cls().available()
            print(f"  {key:14} {'ready' if ok else why:32} {cls.about}")
        runs = sorted(RUNS.glob("*/result.json"))
        print(f"\nSaved runs ({len(runs)}):" if runs else "\nNo saved runs yet: deckos bench system")
        for r in runs[-10:]:
            print("  " + r.parent.name)
        return 0
    if args.command == "experiment":
        keys = list(dict.fromkeys(args.tests.split(",")))
        unknown = [k for k in keys if k not in ALL]
        if unknown:
            parser.error("unknown runner(s): " + ", ".join(unknown) + "; choose " + ", ".join(ALL))
        a, b = run_experiment(args.setting, args.a, args.b, lambda: [ALL[k]() for k in keys],
                              repeat=args.repeat, label=args.label, say=print)
        for run in (a, b):
            Path(run["_folder"], "report.html").write_text(run_report(run), encoding="utf-8")
        out = Path(b["_folder"]) / "experiment.html"
        out.write_text(compare_report(a, b), encoding="utf-8")
        show(out, not args.no_open)
        return 0
    if args.command == "compare":
        (a, _), (b, folder) = load(args.a), load(args.b)
        out = folder / f"compare-{a['id']}.html"
        out.write_text(compare_report(a, b), encoding="utf-8")
        show(out, not args.no_open)
        return 0
    if args.command == "run":
        keys = args.keys.split(",")
        unknown = [k for k in keys if k not in ALL]
        if unknown:
            parser.error("unknown runner(s): " + ", ".join(unknown) + "; choose " + ", ".join(ALL))
        classes = [ALL[k] for k in dict.fromkeys(keys)]
    else:
        classes = SYSTEM if args.command == "system" else GAMES
    result = run_suite([c() for c in classes], repeat=args.repeat, label=args.label, say=print)
    folder = save(result, "custom" if args.command == "run" else args.command)
    (folder / "report.html").write_text(run_report(result), encoding="utf-8")
    show(folder / "report.html", not args.no_open)
    return 0 if any(r["metrics"] and not r["error"] for r in result["results"]) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print(f"deckos bench: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBenchmark interrupted.", file=sys.stderr)
        sys.exit(130)
