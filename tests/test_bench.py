"""Bench lifecycle and command validation; no hardware workloads or system changes."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'pkg/deckos-settings/rootfs/usr/lib/deckos/bench'))
import bench_core as core
import deckos_bench as cli
import runners
from report import run_report, compare_report
import bench_experiment as exp


class BenchTests(unittest.TestCase):
    def test_failed_repetition_is_discarded_and_sensors_stop(self):
        class Failing(core.Runner):
            key, title, group = 'fake', 'Fake', 'cpu'
            calls = 0
            finished = False

            def run(self, result, say):
                self.calls += 1
                result.add('score', 'Score', 'points', self.calls)
                if self.calls == 2:
                    raise RuntimeError('failed halfway')

            def finish(self, say):
                self.finished = True

        runner = Failing()
        with patch.object(core, 'Sensors') as sensors, patch.object(core, 'environment', return_value={}):
            sensors.return_value.start.return_value = sensors.return_value
            sensors.return_value.summary.return_value = {}
            sensors.return_value.trace.return_value = {}
            result = core.run_suite([runner], repeat=3, settle_between=False, say=lambda _: None)
            sensors.return_value.stop.assert_called_once()
        self.assertTrue(runner.finished)
        row = result['results'][0]
        self.assertEqual(row['metrics']['score']['values'], [1.0])
        self.assertEqual(row['error'], 'failed halfway')
        self.assertIn('failed halfway', run_report(result))

    def test_repeat_validation_precedes_work(self):
        with patch.object(core, 'environment') as environment:
            with self.assertRaises(ValueError):
                core.run_suite([], repeat=0)
            environment.assert_not_called()
        for args in (['system', '--repeat', '0'], ['system', '--repeat', 'bad'],
                     ['system', '--unknown'], ['run', 'missing']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    cli.main(args)
                self.assertEqual(error.exception.code, 2)

    def test_disk_owns_only_its_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runners, 'call', return_value='{}') as call:
            existing = Path(folder) / 'deckos-bench.fio'
            existing.write_text('keep me')
            disk = runners.Disk(folder)
            disk.prepare(lambda _: None)
            self.assertNotEqual(disk.filename, existing)
            self.assertIn('--rw=write', call.call_args.args[0])
            work = disk.filename.parent
            disk.finish(lambda _: None)
            self.assertFalse(work.exists())
            self.assertEqual(existing.read_text(), 'keep me')

    def test_report_and_comparison_from_saved_shape(self):
        metric = core.Metric('score', '<Score>', 'points', values=[10, 11, 12])
        result = core.Result('fake', '<CPU>', 'cpu', metrics={'score': metric})
        from dataclasses import asdict
        a = {'id': 'a', 'started': 0, 'seconds': 1, 'repeat': 3, 'environment': {},
             'results': [asdict(result)]}
        self.assertIn('&lt;CPU&gt;', run_report(a))
        self.assertIn('within noise', compare_report(a, dict(a, id='b')))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        from bench_demo import snapshot
        self.runs, _, _ = snapshot()

    def test_bad_history_is_skipped_without_losing_good_runs(self):
        import json
        from bench_data import history
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in [('good', json.dumps(self.runs[0])), ('broken', '{'),
                                  ('invalid', json.dumps(dict(self.runs[0], seconds='bad')))]:
                (root/name).mkdir()
                (root/name/'result.json').write_text(content)
            runs, errors = history(root)
            self.assertEqual(len(runs), 1)
            self.assertEqual(len(errors), 2)

    def test_comparisons_exclude_different_units_and_failed_runners(self):
        from copy import deepcopy
        from bench_data import comparisons
        a, b = deepcopy(self.runs[0]), deepcopy(self.runs[-1])
        self.assertEqual(len(comparisons(a, b)), 6)
        b['results'][0]['error'] = 'failed'
        b['results'][1]['metrics']['triad']['unit'] = 'different'
        rows = comparisons(a, b)
        self.assertEqual(len(rows), 4)
        self.assertNotIn('All cores (total)', [r['name'] for r in rows])

    def test_same_second_saves_do_not_overwrite(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as folder, patch.object(core, 'RUNS', Path(folder)):
            first = core.save(deepcopy(self.runs[0]))
            second = core.save(deepcopy(self.runs[0]))
            self.assertNotEqual(first, second)
            self.assertTrue((first/'result.json').is_file())
            self.assertTrue((second/'result.json').is_file())

    def test_nonfinite_measurements_rejected(self):
        with self.assertRaises(ValueError):
            core.Result('fake', 'Fake', 'cpu').add('bad', 'Bad', 'points', float('nan'))

    def test_beamng_json_schema(self):
        import json
        result = core.Result('game-beamng', 'BeamNG', 'game')
        runners.parse_bananabench(json.dumps({'version': '0.5', 'vehicleMin': 1, 'vehicleMax': 40,
                                             'tests': {'pickup': {'maxMbeams': 340.2, 'maxRealtimeVehicles': 19}}}), result)
        self.assertEqual(result.metrics['pickup_throughput'].values, [340.2])
        self.assertEqual(result.metrics['pickup_realtime'].values, [19])
        with self.assertRaises(RuntimeError):
            runners.parse_bananabench('{"tests": {}}', result)

    def test_experiment_alternates_and_restores_the_setting(self):
        class Toggle(exp.Setting):
            key, name, values = 'toggle', 'Toggle', ('x', 'y')

            def __init__(self):
                self.value, self.history = 'x', []

            def get(self):
                return self.value

            def set(self, value):
                self.value = value
                self.history.append(value)

        class Echo(core.Runner):
            key, title, group = 'echo', 'Echo', 'cpu'
            setting = None

            def run(self, result, say):
                result.add('v', 'Value', 'units', 1.0 if self.setting.value == 'x' else 2.0)

        toggle = Toggle()
        Echo.setting = toggle
        with tempfile.TemporaryDirectory() as tmp, patch.dict(exp.SETTINGS, {'toggle': toggle}), \
                patch.object(core, 'RUNS', Path(tmp)), patch.object(exp, 'settle', lambda **_: None), \
                patch.object(core, 'settle', lambda **_: None), patch.object(core, 'environment', lambda: {}):
            a, b = exp.run_experiment('toggle', 'x', 'y', lambda: [Echo()], repeat=3, say=lambda _t: None)
        self.assertEqual(toggle.history[:6], ['x', 'y', 'y', 'x', 'x', 'y'])  # A B, B A, A B
        self.assertEqual(toggle.value, 'x')                                    # put back afterwards
        self.assertEqual(a['results'][0]['metrics']['v']['values'], [1.0, 1.0, 1.0])
        self.assertEqual(b['results'][0]['metrics']['v']['values'], [2.0, 2.0, 2.0])
        self.assertEqual(core.compare([1.0] * 3, [2.0] * 3)['verdict'], 'better')

    def test_experiment_refuses_the_same_value_twice(self):
        with self.assertRaises(ValueError):
            exp.run_experiment('power', 'balanced', 'balanced', lambda: [], repeat=1, say=lambda _t: None)


if __name__ == '__main__':
    unittest.main()
