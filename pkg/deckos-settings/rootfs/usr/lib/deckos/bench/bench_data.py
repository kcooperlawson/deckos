"""Validated history and presentation data, shared by the native app and its worker."""
import json
import math
from pathlib import Path

from bench_core import RUNS, compare


def valid_run(run):
    if not isinstance(run, dict) or run.get('version') != 1:
        return False
    if not isinstance(run.get('id'), str) or not isinstance(run.get('environment'), dict):
        return False
    if not isinstance(run.get('started'), (int, float)) or not math.isfinite(run['started']):
        return False
    if not isinstance(run.get('label', ''), str) or not isinstance(run.get('kind', ''), str):
        return False
    if not isinstance(run.get('repeat'), int) or run['repeat'] < 1:
        return False
    if not isinstance(run.get('seconds'), (int, float)) or not math.isfinite(run['seconds']) or run['seconds'] < 0:
        return False
    if not isinstance(run.get('results'), list):
        return False
    try:
        for result in run['results']:
            if not isinstance(result['title'], str) or not isinstance(result.get('error', ''), str):
                return False
            if not isinstance(result.get('sensors', {}), dict):
                return False
            for sensor in result.get('sensors', {}).values():
                if not isinstance(sensor, dict) or not all(isinstance(sensor.get(k), (int, float)) and
                                                           math.isfinite(sensor[k]) for k in ('avg', 'max')):
                    return False
            if not isinstance(result['runner'], str) or not isinstance(result['metrics'], dict):
                return False
            for metric in result['metrics'].values():
                values = metric['values']
                if not isinstance(values, list) or not values:
                    return False
                if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
                    return False
                if not all(isinstance(metric[k], str) for k in ('key', 'name', 'unit')):
                    return False
                if not isinstance(metric['higher_better'], bool):
                    return False
    except (KeyError, TypeError):
        return False
    return True


def history(root=RUNS):
    runs, errors = [], []
    for file in Path(root).glob('*/result.json'):
        try:
            if file.stat().st_size > 20_000_000:
                raise ValueError('file is too large')
            run = json.loads(file.read_text())
            if not valid_run(run):
                raise ValueError('unsupported or incomplete result')
            run['_folder'] = str(file.parent)
            runs.append(run)
        except (OSError, ValueError, TypeError) as error:
            errors.append(f'{file.parent.name}: {error}')
    return sorted(runs, key=lambda r: r['started']), errors


def title(run):
    return run.get('label') or run.get('id', 'Untitled run')


def metrics(run):
    """Only completed runners contribute to trends and comparisons."""
    for result in run['results']:
        if result.get('error'):
            continue
        for key, metric in result['metrics'].items():
            if metric['values']:
                yield result, key, metric


def signature(result, key, metric):
    return (result['runner'], key, metric['name'], metric['unit'], metric['higher_better'])


def series(runs):
    found = {}
    for run in runs:
        for result, key, metric in metrics(run):
            sig = signature(result, key, metric)
            found.setdefault(sig, {'name': f"{result['title']} · {metric['name']}", 'unit': metric['unit'],
                                   'higher': metric['higher_better'], 'points': []})['points'].append(
                (run['started'], sum(metric['values']) / len(metric['values']), title(run)))
    return list(found.values())


def comparisons(a, b):
    old = {signature(r, k, m): m for r, k, m in metrics(a)}
    rows = []
    for result, key, metric in metrics(b):
        before = old.get(signature(result, key, metric))
        if not before or sum(before['values']) == 0:
            continue
        verdict = compare(before['values'], metric['values'], metric['higher_better'])
        rows.append(dict(verdict, name=metric['name'], runner=result['title'], unit=metric['unit'],
                         a=sum(before['values']) / len(before['values']),
                         b=sum(metric['values']) / len(metric['values'])))
    return rows
