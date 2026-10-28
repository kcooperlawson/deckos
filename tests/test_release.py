"""Builder's release brakes (builder/release.py): what stops a release before anything is pushed or tagged."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pkg/deckos-settings/rootfs/usr/lib/deckos/builder"))
import release  # noqa: E402

NOW = 1_800_000_000
READY = {"branch": "main", "version": "0.17.6", "changed": [], "behind": 0, "last_tag_at": NOW - 20 * 3600}


class ReleaseTests(unittest.TestCase):
    def test_a_clean_main_a_day_later_can_release(self):
        self.assertEqual(release.problems(READY, "0.17.7", now=NOW), [])

    def test_one_release_a_day_unless_hotfix(self):
        soon = dict(READY, last_tag_at=NOW - 2 * 3600)
        why = release.problems(soon, "0.17.7", now=NOW)
        self.assertEqual(len(why), 1)
        self.assertIn("hotfix", why[0])
        self.assertEqual(release.problems(soon, "0.17.7", hotfix=True, now=NOW), [])

    def test_first_release_has_no_gap(self):
        self.assertEqual(release.problems(dict(READY, last_tag_at=0), "0.17.7", now=NOW), [])

    def test_what_stops_it(self):
        bad = dict(READY, branch="vibe", changed=["README.md"], behind=2)
        why = " ".join(release.problems(bad, "0.17.6", now=NOW))
        for words in ("from main", "README.md", "pull first", "newer than 0.17.6"):
            self.assertIn(words, why)

    def test_versions_compare_as_numbers(self):
        self.assertEqual(release.problems(dict(READY, version="0.9.9"), "0.10.0", now=NOW), [])
        self.assertTrue(release.problems(READY, "0.17", now=NOW))


if __name__ == "__main__":
    unittest.main()
