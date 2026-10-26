"""The DecKoOS Score: the reference PC scores exactly 5,000, twice as fast is twice the points, it's only a full score
with all five parts measured with the score's own AI model, and one odd repetition doesn't move it."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'pkg/deckos-settings/rootfs/usr/lib/deckos/bench'))
import score as SC  # noqa: E402


def reference_run(times=1.0, reps=3):
    """A saved run whose every measurement is the reference value (times the factor, the right way round)."""
    results = []
    for key, (_name, runner, spec, _w) in SC.PARTS.items():
        metrics = {}
        for metric, _wt, ref, higher in spec:
            v = ref * times if higher else ref / times
            name = f'Writing ({SC.AI_MODEL})' if metric == 'generate' else metric
            metrics[metric] = {'key': metric, 'name': name, 'unit': 'x', 'higher_better': higher, 'values': [v] * reps}
        results.append({'runner': runner, 'title': runner, 'group': key, 'metrics': metrics, 'error': ''})
    return {'version': 1, 'results': results}


class ScoreTests(unittest.TestCase):
    def test_the_reference_pc_scores_5000(self):
        s = SC.score(reference_run())
        self.assertTrue(s['complete'])
        self.assertEqual(s['total'], SC.BASE)
        self.assertEqual({p['score'] for p in s['parts'].values()}, {SC.BASE})
        self.assertEqual(SC.headline(s), ('5,000', 'DecKoOS Score'))

    def test_twice_as_fast_is_twice_the_points(self):
        self.assertEqual(SC.score(reference_run(2.0))['total'], 2 * SC.BASE)
        # Lower latency is better: half the latency, with everything else at the reference, raises memory's score
        run = reference_run()
        mem = next(r for r in run['results'] if r['runner'] == 'memory')
        mem['metrics']['latency']['values'] = [45.0] * 3
        self.assertGreater(SC.part(run, 'memory')['score'], SC.BASE)

    def test_weights_add_up(self):
        self.assertAlmostEqual(sum(p[3] for p in SC.PARTS.values()), 1.0)
        for name, _runner, spec, _w in SC.PARTS.values():
            with self.subTest(part=name):
                self.assertAlmostEqual(sum(w for _, w, _, _ in spec), 1.0)

    def test_another_ai_model_is_only_a_partial_score(self):
        run = reference_run()
        ai = next(r for r in run['results'] if r['runner'] == 'ai-ollama')
        ai['metrics']['generate']['name'] = 'Writing (gpt-oss:20b)'
        s = SC.score(run)
        self.assertIsNone(s['total'])
        self.assertEqual(s['partial'], SC.BASE)
        self.assertIn(SC.AI_MODEL, s['parts']['ai']['missing'])
        self.assertEqual(SC.headline(s)[1], 'Partial score')

    def test_a_failed_part_is_left_out(self):
        run = reference_run()
        next(r for r in run['results'] if r['runner'] == 'gpu-vkmark')['error'] = 'needs vkmark'
        s = SC.score(run)
        self.assertFalse(s['complete'])
        self.assertEqual(s['parts']['graphics'], {'missing': 'needs vkmark'})
        self.assertEqual(SC.headline(SC.score({'results': []})), ('—', 'No score yet'))

    def test_medians_and_the_range(self):
        run = reference_run()
        cpu = next(r for r in run['results'] if r['runner'] == 'cpu-7z')
        cpu['metrics']['multi']['values'] = [60000, 60000, 30000]  # one bad repetition
        p = SC.part(run, 'cpu')
        self.assertEqual(p['score'], SC.BASE, 'the median ignores the odd one out')
        self.assertLess(p['low'], SC.BASE)
        self.assertEqual(p['high'], SC.BASE)

    def test_scores_are_stable(self):
        # Version 1's numbers must never change for the same measurements: history depends on it
        run = deepcopy(reference_run(1.7))
        self.assertEqual(SC.score(run)['total'], 8500)
        self.assertEqual(SC.VERSION, 1)


if __name__ == '__main__':
    unittest.main()
