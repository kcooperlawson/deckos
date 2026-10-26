"""JSON-lines worker: keeps probing, benchmarking and statistics off the GUI thread."""
import argparse
import json
import os
import signal
import sys
import threading
from dataclasses import asdict
from pathlib import Path

from bench_core import RUNS, environment, load, run_suite, save
from bench_data import comparisons, history, valid_run
from report import run_report
from runners import ALL


def emit(event, **data):
    print(json.dumps(dict(event=event, **data), allow_nan=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['scan', 'run', 'compare', 'experiment', 'score'])
    parser.add_argument('--setting')
    parser.add_argument('--value-a')
    parser.add_argument('--value-b')
    parser.add_argument('--keys', default='')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--label', default='')
    parser.add_argument('--a')
    parser.add_argument('--b')
    args = parser.parse_args()
    if os.name == 'posix' and os.getpgrp() != os.getpid():
        os.setsid()
    emit('ready')
    if args.command == 'scan':
        runs, errors = history()
        emit('history', runs=runs, errors=errors)
        statuses = {}
        for key, cls in ALL.items():
            try:
                ok, why = cls().available()
            except Exception as error:
                ok, why = False, str(error)
            statuses[key] = dict(available=ok, reason=why)
        emit('snapshot', environment=environment(), runners=statuses)
    elif args.command == 'compare':
        a, _ = load(args.a)
        b, _ = load(args.b)
        if not valid_run(a) or not valid_run(b):
            raise ValueError('These saved results are not supported')
        emit('comparison', rows=comparisons(a, b))
    else:
        import fcntl
        RUNS.mkdir(parents=True, exist_ok=True)
        lock = (RUNS / '.app-run.lock').open('w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Bench window is already running a benchmark')
        cancelled = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: cancelled.set())
        signal.signal(signal.SIGINT, lambda *_: cancelled.set())
        if args.command == 'score':
            # The DecKoOS Score: every system test, the score's own AI model, three repetitions, always
            from runners import score_runners
            from score import score
            run = run_suite(score_runners(), repeat=3, label=args.label or 'DecKoOS Score',
                            say=lambda text: emit('log', text=text), cancelled=cancelled.is_set,
                            on_result=lambda result: emit('result', result=asdict(result)),
                            on_progress=lambda index, total, key, repetition, repeat: emit(
                                'progress', index=index, total=total, key=key, repetition=repetition, repeat=repeat))
            run['score'] = score(run)
            folder = save(run, 'score')
            (folder / 'report.html').write_text(run_report(run), encoding='utf-8')
            emit('saved', folder=str(folder), run=dict(run, _folder=str(folder)))
            lock.close()
            return
        keys = list(dict.fromkeys(args.keys.split(',')))
        if not keys or any(key not in ALL for key in keys):
            raise ValueError('Choose at least one supported benchmark')
        progress = lambda index, total, key, repetition, repeat: emit(
            'progress', index=index, total=total, key=key, repetition=repetition, repeat=repeat)
        if args.command == 'experiment':
            from bench_experiment import run_experiment
            a, b = run_experiment(args.setting, args.value_a, args.value_b, lambda: [ALL[key]() for key in keys],
                                  repeat=args.repeat, label=args.label, say=lambda text: emit('log', text=text),
                                  cancelled=cancelled.is_set, on_progress=progress)
            for run in (a, b):
                (Path(run['_folder']) / 'report.html').write_text(run_report(run), encoding='utf-8')
                emit('saved', folder=run['_folder'], run=run)
            emit('experiment', a=a['id'], b=b['id'])
            lock.close()
            return
        run = run_suite([ALL[key]() for key in keys], repeat=args.repeat, label=args.label,
                        say=lambda text: emit('log', text=text), cancelled=cancelled.is_set,
                        on_result=lambda result: emit('result', result=asdict(result)),
                        on_progress=lambda index, total, key, repetition, repeat: emit(
                            'progress', index=index, total=total, key=key, repetition=repetition, repeat=repeat))
        folder = save(run, 'custom')
        (folder / 'report.html').write_text(run_report(run), encoding='utf-8')
        emit('saved', folder=str(folder), run=dict(run, _folder=str(folder)))
        lock.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        emit('error', text=str(error) or type(error).__name__)
        sys.exit(1)
