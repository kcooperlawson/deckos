"""Offscreen native UI smoke tests; demo mode must never start hardware workers."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'pkg/deckos-settings/rootfs/usr/lib/deckos/bench'))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import bench_app


class BenchUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(bench_app.stylesheet())

    def setUp(self):
        self.worker = patch.object(bench_app.Worker, 'launch')
        self.launch = self.worker.start()
        self.window = bench_app.Bench(demo=True)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        if self.window.busy:
            self.window.stop_run()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.launch.assert_not_called()
        self.worker.stop()

    def test_navigation_search_and_baseline(self):
        QTest.mouseClick(self.window.nav['history'], Qt.LeftButton)
        self.assertEqual(self.window.stack.currentIndex(), 2)
        self.window.search.setText('fresh boot')
        self.assertEqual(self.window.history_table.rowCount(), 1)
        self.assertEqual(self.window.selected['label'], 'Fresh boot')
        self.window.use_baseline()
        self.assertEqual(self.window.compare_a.currentData(), 'demo-1')
        self.assertEqual(self.window.stack.currentIndex(), 3)
        self.assertEqual(self.window.compare_table.rowCount(), 6)
        self.window.search.setText('no matching sessions')
        self.assertEqual(self.window.history_table.rowCount(), 0)
        self.assertFalse(self.window.report_button.isEnabled())

    def test_same_session_cannot_be_compared(self):
        self.window.compare_a.setCurrentIndex(self.window.compare_b.currentIndex())
        self.assertEqual(self.window.compare_table.rowCount(), 0)
        self.assertFalse(self.window.compare_export.isEnabled())

    def test_demo_start_stop_and_repeat_controls(self):
        self.window.repeat.setValue(5)
        self.assertIn('16 min', self.window.estimate.text())
        self.window.start_run()
        self.assertTrue(self.window.busy)
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.repeat.isEnabled())
        self.window.stop_run()
        self.assertFalse(self.window.busy)
        self.assertTrue(self.window.repeat.isEnabled())
        self.assertEqual(len(self.window.runs), 6)

    def test_export_is_self_contained_html(self):
        with tempfile.TemporaryDirectory() as folder:
            out = str(Path(folder) / 'report.html')
            with patch.object(bench_app.QFileDialog, 'getSaveFileName', return_value=(out, 'HTML')), \
                 patch.object(bench_app.QDesktopServices, 'openUrl'):
                self.window.export_run()
            text = Path(out).read_text()
            self.assertIn('Tuned baseline', text)
            self.assertIn('<svg', text)
            self.assertNotIn('<script', text)


if __name__ == '__main__':
    unittest.main()
